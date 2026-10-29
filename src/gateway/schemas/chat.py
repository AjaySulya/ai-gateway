from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# OpenAI-compatible parameters that are safe to forward to LiteLLM. Anything
# else is accepted by the parser (extra="allow") but deliberately dropped
# before the provider call. In particular, routing/transport settings such as
# api_base, api_key, custom_llm_provider, headers, and timeout belong to the
# stored Provider row, not to the caller: forwarding them would let a request
# redirect the provider call and leak the provider credential.
PASSTHROUGH_FIELDS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "n",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "top_logprobs",
        "user",
        "seed",
        "response_format",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "stream_options",
        "service_tier",
        "store",
        "metadata",
        "modalities",
        "audio",
        "prediction",
        "reasoning_effort",
        # Legacy function-calling shape; LiteLLM still accepts it.
        "functions",
        "function_call",
    }
)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")  # unknown fields are parsed, then filtered

    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None

    def provider_params(self) -> dict[str, Any]:
        """Return only whitelisted OpenAI parameters to forward to LiteLLM.

        Unknown fields are intentionally not passed through. Routing and
        transport options must come from the Provider record, never from the
        request body.
        """
        dumped = self.model_dump(exclude={"model", "messages", "stream"}, exclude_none=True)
        return {key: value for key, value in dumped.items() if key in PASSTHROUGH_FIELDS}
