import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.auth import resolve_api_key
from gateway.data_plane.context import RequestContext
from gateway.db.models import UsageStatus
from gateway.db.session import get_db
from gateway.observability.otel import tracer
from gateway.policy.resolution import resolve_effective_policy
from gateway.rate_limit.enforcement import check_rate_limit
from gateway.rate_limit.limiter import WINDOW_SECONDS
from gateway.routing.router import route_chat_completion
from gateway.schemas.chat import ChatCompletionRequest
from gateway.security.content_filter import detect_prompt_injection, redact_pii
from gateway.security.request_analyzer import analyze_request
from gateway.usage.budgets import check_budget
from gateway.usage.tracker import extract_usage_and_cost, record_usage, record_usage_standalone

router = APIRouter(prefix="/v1", tags=["data-plane"])
logger = logging.getLogger(__name__)


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    context: RequestContext = Depends(resolve_api_key),
    db: AsyncSession = Depends(get_db),
):
    context.model_requested = payload.model
    start = time.monotonic()

    # Each stage gets its own child span, nested under FastAPIInstrumentor's
    # auto-created root span for this request - that's what makes "how long
    # did the policy check take on this specific slow request" answerable
    # instead of just "the request took 400ms" as one opaque number.
    # Raising inside a span is enough for OTel to record it as an error on
    # that span; no manual span.set_status() needed at each raise below.

    # Rate Limiting runs before the Policy Engine, matching the architecture
    # diagram's stage order (Authentication -> Request Context -> Rate
    # Limiting -> Policy Engine -> ... -> Model Router). Phases 3 and 5
    # landed before this one existed, so this is also the point where the
    # handler's actual order caught up to what the diagram always specified.
    with tracer.start_as_current_span("rate_limit"):
        rate_limited, rl_scope, rl_limit, rl_count = await check_rate_limit(db, context)
    if rate_limited:
        retry_after = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        logger.warning(
            "rate limited: scope=%s count=%d limit=%d project=%s",
            rl_scope,
            rl_count,
            rl_limit,
            context.project_id,
        )
        await record_usage(
            db,
            context,
            provider_id=None,
            status=UsageStatus.error,
            latency_ms=_elapsed_ms(start),
            error_message=f"rate_limited: {rl_scope} at {rl_count}/{rl_limit} rpm",
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded for {rl_scope}: {rl_count}/{rl_limit} requests this minute",
            headers={"Retry-After": str(retry_after)},
        )

    # Policy Engine runs before the Model Router, matching the pipeline
    # order in the architecture diagram - a disallowed model never reaches
    # candidate resolution, retries, or a provider call.
    with tracer.start_as_current_span("policy_engine"):
        effective_policy = await resolve_effective_policy(
            db, context.organization_id, context.team_id, context.project_id, context.agent_id
        )
    if not effective_policy.allows_model(payload.model):
        logger.warning("policy denied: model=%s project=%s", payload.model, context.project_id)
        await record_usage(
            db,
            context,
            provider_id=None,
            status=UsageStatus.error,
            latency_ms=_elapsed_ms(start),
            error_message=f"policy_denied: model '{payload.model}' not permitted",
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Model '{payload.model}' is not permitted by policy"
        )

    with tracer.start_as_current_span("budget_check"):
        over_budget, scope, cap, spent = await check_budget(db, context)
    if over_budget:
        logger.warning(
            "budget exceeded: scope=%s spent=%.4f cap=%.4f project=%s",
            scope,
            spent,
            cap,
            context.project_id,
        )
        await record_usage(
            db,
            context,
            provider_id=None,
            status=UsageStatus.error,
            latency_ms=_elapsed_ms(start),
            error_message=f"budget_exceeded: {scope} spent ${spent:.2f} of ${cap:.2f} cap",
        )
        # 402: closer to what actually happened than reusing 429 (Phase 6's
        # rate limiter) or 403 (policy, above) for a budget ceiling.
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Budget exceeded for {scope}: ${spent:.2f} of ${cap:.2f}",
        )

    messages = [m.model_dump() for m in payload.messages]
    extra = payload.model_dump(exclude={"model", "messages", "stream"}, exclude_none=True)

    # Request Analyzer before Security Engine - deliberately reversed from
    # the architecture diagram's literal box order (Security Engine, then
    # Request Analyzer). Running regex-based content scanning before basic
    # size validation would let an oversized payload hit the more expensive
    # check first, undermining the cheap check's own purpose. See
    # gateway.security's package docstring.
    with tracer.start_as_current_span("request_analyzer"):
        try:
            analyze_request(messages)
        except HTTPException as exc:
            await record_usage(
                db,
                context,
                provider_id=None,
                status=UsageStatus.error,
                latency_ms=_elapsed_ms(start),
                error_message=f"request_analyzer: {exc.detail}",
            )
            raise

    with tracer.start_as_current_span("security_engine") as security_span:
        injection_hits = detect_prompt_injection(messages)
        if injection_hits:
            logger.warning(
                "prompt injection patterns detected: count=%d project=%s",
                len(injection_hits),
                context.project_id,
            )
            security_span.set_attribute("gateway.injection_detected", True)
            if effective_policy.block_prompt_injection:
                await record_usage(
                    db,
                    context,
                    provider_id=None,
                    status=UsageStatus.error,
                    latency_ms=_elapsed_ms(start),
                    error_message="security_blocked: prompt injection pattern detected",
                )
                # Generic message deliberately - see content_filter.py on
                # not handing back which pattern matched.
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Request blocked: content matched a security policy",
                )

        redacted_messages, pii_kinds = redact_pii(messages)
        if pii_kinds:
            security_span.set_attribute("gateway.pii_detected", pii_kinds)
            if effective_policy.redact_pii:
                logger.warning("PII redacted: kinds=%s project=%s", pii_kinds, context.project_id)
                messages = redacted_messages
            else:
                logger.warning(
                    "PII detected but not redacted (redact_pii not enabled): kinds=%s project=%s",
                    pii_kinds,
                    context.project_id,
                )

    with tracer.start_as_current_span("model_router") as span:
        span.set_attribute("gateway.model_requested", payload.model)
        try:
            result, provider = await route_chat_completion(
                db, context.project_id, payload.model, messages, stream=payload.stream, extra=extra
            )
        except HTTPException as exc:
            logger.error(
                "routing failed: model=%s project=%s detail=%s",
                payload.model,
                context.project_id,
                exc.detail,
            )
            await record_usage(
                db,
                context,
                provider_id=None,
                status=UsageStatus.error,
                latency_ms=_elapsed_ms(start),
                error_message=str(exc.detail),
            )
            raise
        span.set_attribute("gateway.provider", provider.name)

    if payload.stream:
        return StreamingResponse(
            _to_sse_with_usage(result, context, provider.id, start),
            media_type="text/event-stream",
        )

    input_tokens, output_tokens, total_tokens, cost_usd = extract_usage_and_cost(result)
    logger.info(
        "chat completion succeeded: model=%s provider=%s project=%s tokens=%s cost=%s",
        payload.model,
        provider.name,
        context.project_id,
        total_tokens,
        cost_usd,
    )
    await record_usage(
        db,
        context,
        provider_id=provider.id,
        status=UsageStatus.success,
        latency_ms=_elapsed_ms(start),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )
    return result.model_dump() if hasattr(result, "model_dump") else result


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def _to_sse_with_usage(
    chunks: AsyncIterator[Any], context: RequestContext, provider_id, start: float
) -> AsyncIterator[str]:
    # Best-effort: only logged if a chunk actually carries a usage field
    # (e.g. OpenAI with stream_options={"include_usage": True}, or
    # Anthropic's final message_delta as LiteLLM normalizes it). Many
    # streaming responses never expose this - tokens/cost are None on
    # those, by design, rather than guessed at.
    captured_usage: dict | None = None
    error_message: str | None = None
    try:
        async for chunk in chunks:
            data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
            usage = data.get("usage") if isinstance(data, dict) else None
            if usage:
                captured_usage = usage
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        input_tokens = output_tokens = total_tokens = None
        if captured_usage:
            input_tokens = captured_usage.get("prompt_tokens")
            output_tokens = captured_usage.get("completion_tokens")
            total_tokens = captured_usage.get("total_tokens")
        if error_message:
            logger.error("streaming chat completion failed: %s", error_message)
        await record_usage_standalone(
            context,
            provider_id=provider_id,
            status=UsageStatus.error if error_message else UsageStatus.success,
            latency_ms=_elapsed_ms(start),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=None,  # cost calc for streaming needs the full response; not attempted here
            error_message=error_message,
        )
