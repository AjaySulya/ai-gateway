import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.auth import resolve_api_key
from gateway.data_plane.context import RequestContext
from gateway.data_plane.litellm_adapter import call_provider, resolve_credential
from gateway.data_plane.model_resolution import resolve_model
from gateway.db.session import get_db
from gateway.policy.resolution import resolve_effective_policy
from gateway.schemas.chat import ChatCompletionRequest

router = APIRouter(prefix="/v1", tags=["data-plane"])


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    context: RequestContext = Depends(resolve_api_key),
    db: AsyncSession = Depends(get_db),
):
    context.model_requested = payload.model

    # Policy Engine runs before the Model Router, matching the pipeline order
    # in the architecture diagram - a disallowed model never reaches routing.
    effective_policy = await resolve_effective_policy(
        db, context.organization_id, context.team_id, context.project_id, context.agent_id
    )
    if not effective_policy.allows_model(payload.model):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Model '{payload.model}' is not permitted by policy"
        )

    model, provider = await resolve_model(db, context.project_id, payload.model)
    api_key = resolve_credential(provider)

    messages = [m.model_dump() for m in payload.messages]
    extra = payload.model_dump(exclude={"model", "messages", "stream"}, exclude_none=True)
    # Provider-level defaults (e.g. a HuggingFace endpoint's api_base) apply
    # unless the request itself specifies the same key.
    extra = {**provider.extra_config, **extra}

    if payload.stream:
        stream = await call_provider(
            model_name=model.model_name,
            provider_type=provider.provider_type.value,
            api_key=api_key,
            messages=messages,
            stream=True,
            **extra,
        )
        return StreamingResponse(_to_sse(stream), media_type="text/event-stream")

    response = await call_provider(
        model_name=model.model_name,
        provider_type=provider.provider_type.value,
        api_key=api_key,
        messages=messages,
        stream=False,
        **extra,
    )
    return response.model_dump() if hasattr(response, "model_dump") else response


async def _to_sse(chunks: AsyncIterator[Any]) -> AsyncIterator[str]:
    async for chunk in chunks:
        data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk
        yield f"data: {json.dumps(data)}\n\n"
    yield "data: [DONE]\n\n"
