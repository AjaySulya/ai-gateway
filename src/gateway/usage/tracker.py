import uuid
from typing import Any

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.context import RequestContext
from gateway.db.models import UsageRecord, UsageStatus
from gateway.db.session import AsyncSessionLocal


def extract_usage_and_cost(
    response: Any,
) -> tuple[int | None, int | None, int | None, float | None]:
    """Pulls token counts and computes cost for a non-streaming LiteLLM
    response. Cost uses litellm.completion_cost(), which looks up per-model
    pricing from LiteLLM's bundled pricing table - not worth hand-rolling.
    """
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None
    try:
        cost_usd = litellm.completion_cost(completion_response=response)
    except Exception:
        # Unrecognized model in LiteLLM's pricing table, or a response shape
        # completion_cost doesn't handle - log the tokens without a dollar
        # figure rather than failing the whole request over a cost estimate.
        cost_usd = None
    return input_tokens, output_tokens, total_tokens, cost_usd


async def record_usage(
    db: AsyncSession,
    context: RequestContext,
    *,
    provider_id: uuid.UUID | None,
    status: UsageStatus,
    latency_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    error_message: str | None = None,
) -> None:
    db.add(
        UsageRecord(
            request_id=context.request_id,
            organization_id=context.organization_id,
            team_id=context.team_id,
            project_id=context.project_id,
            agent_id=context.agent_id,
            api_key_id=context.api_key_id,
            provider_id=provider_id,
            model_name=context.model_requested or "unknown",
            status=status,
            error_message=error_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
    )
    await db.commit()


async def record_usage_standalone(context: RequestContext, **kwargs: Any) -> None:
    """For logging after a StreamingResponse has already started sending.

    Starlette tears down `yield`-based dependencies (like Depends(get_db))
    once the route handler *returns* - which, for a StreamingResponse,
    happens before the streamed body has finished sending. Using the
    request-scoped session inside the generator that runs afterward hits a
    closed session. This opens a fresh, short-lived one instead.
    """
    async with AsyncSessionLocal() as db:
        await record_usage(db, context, **kwargs)
