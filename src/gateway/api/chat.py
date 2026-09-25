import json
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
from gateway.policy.resolution import resolve_effective_policy
from gateway.routing.router import route_chat_completion
from gateway.schemas.chat import ChatCompletionRequest
from gateway.usage.budgets import check_budget
from gateway.usage.tracker import extract_usage_and_cost, record_usage, record_usage_standalone

router = APIRouter(prefix="/v1", tags=["data-plane"])


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    context: RequestContext = Depends(resolve_api_key),
    db: AsyncSession = Depends(get_db),
):
    context.model_requested = payload.model
    start = time.monotonic()

    # Policy Engine runs before the Model Router, matching the pipeline
    # order in the architecture diagram - a disallowed model never reaches
    # candidate resolution, retries, or a provider call.
    effective_policy = await resolve_effective_policy(
        db, context.organization_id, context.team_id, context.project_id, context.agent_id
    )
    if not effective_policy.allows_model(payload.model):
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

    over_budget, scope, cap, spent = await check_budget(db, context)
    if over_budget:
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

    try:
        result, provider = await route_chat_completion(
            db, context.project_id, payload.model, messages, stream=payload.stream, extra=extra
        )
    except HTTPException as exc:
        await record_usage(
            db,
            context,
            provider_id=None,
            status=UsageStatus.error,
            latency_ms=_elapsed_ms(start),
            error_message=str(exc.detail),
        )
        raise

    if payload.stream:
        return StreamingResponse(
            _to_sse_with_usage(result, context, provider.id, start),
            media_type="text/event-stream",
        )

    input_tokens, output_tokens, total_tokens, cost_usd = extract_usage_and_cost(result)
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
