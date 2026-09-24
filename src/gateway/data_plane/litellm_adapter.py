import os
from typing import Any

import litellm
from fastapi import HTTPException, status

from gateway.db.models import Provider


def resolve_credential(provider: Provider) -> str:
    """Provider.credential_ref names an environment variable holding the
    actual provider API key - a stand-in for a real secrets manager, which
    is a later hardening pass (Phase 10). Call sites don't need to change
    when that lands; only this function does."""
    api_key = os.environ.get(provider.credential_ref)
    if not api_key:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Credential '{provider.credential_ref}' is not set in the gateway's environment",
        )
    return api_key


async def call_provider(
    *,
    model_name: str,
    provider_type: str,
    api_key: str,
    messages: list[dict[str, Any]],
    stream: bool,
    **kwargs: Any,
):
    # custom_llm_provider makes routing explicit rather than relying on
    # LiteLLM's model-name pattern matching, since Provider.provider_type is
    # already known from the Control API record.
    return await litellm.acompletion(
        model=model_name,
        custom_llm_provider=provider_type,
        api_key=api_key,
        messages=messages,
        stream=stream,
        **kwargs,
    )
