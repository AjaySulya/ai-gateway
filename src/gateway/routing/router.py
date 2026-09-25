"""Orchestrates strategies.get_candidates() and circuit_breaker.py into the
actual routed call: skip candidates with an open circuit, retry transient
errors on the same candidate with backoff, and fall back to the next
candidate on exhausted retries or a non-retryable error.

Streaming note: a failure can only trigger fallback if it happens before or
during the *first chunk* of the stream. Once a chunk has been forwarded to
the client, we've committed to that provider for the rest of the response -
there's no way to swap providers mid-stream without the client seeing a
glitch or duplicate content. This is a real, known limitation, not an
oversight.
"""

import asyncio
import random
import uuid
from typing import Any, AsyncIterator

import litellm
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.litellm_adapter import call_provider, resolve_credential
from gateway.db.models import Model, Provider
from gateway.routing import circuit_breaker
from gateway.routing.strategies import get_candidates

MAX_RETRIES_PER_CANDIDATE = 2
BASE_BACKOFF_SECONDS = 0.5

# Per LiteLLM's documented exception mapping (top-level litellm.<Name>).
# Worth a manual check against `uv sync`'s resolved litellm version if these
# don't match - this is the one place the router depends on LiteLLM's exact
# exception surface, and it hasn't been verified against a live install in
# this environment.
RETRYABLE_EXCEPTIONS = (
    litellm.Timeout,
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.APIConnectionError,
    litellm.InternalServerError,
)


def _backoff_seconds(attempt: int) -> float:
    return BASE_BACKOFF_SECONDS * (2**attempt) + random.uniform(0, 0.25)


async def _call_with_retries_non_streaming(
    model: Model, provider: Provider, api_key: str, messages: list[dict], call_kwargs: dict
):
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES_PER_CANDIDATE + 1):
        try:
            return await call_provider(
                model_name=model.model_name,
                provider_type=provider.provider_type.value,
                api_key=api_key,
                messages=messages,
                stream=False,
                **call_kwargs,
            )
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            if attempt == MAX_RETRIES_PER_CANDIDATE:
                raise
            await asyncio.sleep(_backoff_seconds(attempt))
    raise last_error  # pragma: no cover - loop above always returns or raises


async def _call_with_retries_streaming(
    model: Model, provider: Provider, api_key: str, messages: list[dict], call_kwargs: dict
):
    """Retries cover getting the stream *started*, including fetching the
    first chunk - many providers only surface auth/connection errors once
    you actually pull from the stream, not at call time."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES_PER_CANDIDATE + 1):
        try:
            raw_stream = await call_provider(
                model_name=model.model_name,
                provider_type=provider.provider_type.value,
                api_key=api_key,
                messages=messages,
                stream=True,
                **call_kwargs,
            )
            first_chunk = await raw_stream.__anext__()
            return first_chunk, raw_stream
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            if attempt == MAX_RETRIES_PER_CANDIDATE:
                raise
            await asyncio.sleep(_backoff_seconds(attempt))
    raise last_error  # pragma: no cover - loop above always returns or raises


async def _prepend(first: Any, rest: AsyncIterator[Any]) -> AsyncIterator[Any]:
    yield first
    async for item in rest:
        yield item


async def route_chat_completion(
    db: AsyncSession,
    project_id: uuid.UUID,
    requested_model_name: str,
    messages: list[dict],
    stream: bool,
    extra: dict[str, Any],
) -> tuple[Any, Provider]:
    """Returns (response_or_stream, provider) - the provider is returned
    alongside the result so callers (usage tracking) can attribute the
    request without re-deriving which candidate actually won."""
    candidates = await get_candidates(db, project_id, requested_model_name)
    if not candidates:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Model '{requested_model_name}' is not available for this project",
        )

    attempted: list[str] = []
    last_error: Exception | None = None

    for model, provider in candidates:
        if await circuit_breaker.is_open(provider.id):
            attempted.append(f"{provider.name} (circuit open)")
            continue

        api_key = resolve_credential(provider)
        # Provider-level defaults (e.g. a HuggingFace endpoint's api_base)
        # apply unless the request itself specifies the same key.
        call_kwargs = {**provider.extra_config, **extra}
        attempted.append(provider.name)

        try:
            if stream:
                first_chunk, raw_stream = await _call_with_retries_streaming(
                    model, provider, api_key, messages, call_kwargs
                )
                await circuit_breaker.record_success(provider.id)
                return _prepend(first_chunk, raw_stream), provider

            response = await _call_with_retries_non_streaming(
                model, provider, api_key, messages, call_kwargs
            )
            await circuit_breaker.record_success(provider.id)
            return response, provider
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any
            # failure on this candidate should fall through to the next one
            last_error = exc
            await circuit_breaker.record_failure(provider.id)
            continue

    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        f"All candidates failed for model '{requested_model_name}'. "
        f"Attempted: {attempted}. Last error: {last_error}",
    )
