from pydantic import BaseModel, ConfigDict


class PolicyConfig(BaseModel):
    """Shape of Policy.config. Every field is optional, and unset means
    'this policy adds no restriction here' - not 'reset to unrestricted'.
    Only an explicit value narrows what a parent scope already set."""

    model_config = ConfigDict(extra="ignore")

    allowed_models: list[str] | None = None
    denied_models: list[str] | None = None
    budget_limit_usd: float | None = None
    rate_limit_rpm: int | None = None
    allowed_regions: list[str] | None = None
    # Phase 8: both default to "off" when unset anywhere in the hierarchy -
    # opt-in, so a project with no security policy behaves exactly as it
    # did before this phase existed. See merge.py for why True is sticky
    # once any level sets it.
    block_prompt_injection: bool | None = None
    redact_pii: bool | None = None


class EffectivePolicy(BaseModel):
    """Result of folding every enabled policy from org down to agent. None
    in allowed_models/allowed_regions/budget/rate_limit means unrestricted
    at that field; denied_models is always a concrete (possibly empty) list.
    block_prompt_injection/redact_pii are always concrete bools (default
    False) - there's no "unrestricted" reading of a boolean the way there
    is for a list, so unlike denied_models there's no ambiguity to resolve.

    Only allowed_models/denied_models are enforced today, in
    /v1/chat/completions. budget_limit_usd and rate_limit_rpm are resolved
    correctly but not yet checked against anything - that needs Phase 5's
    usage tracking and Phase 6's rate limiter, respectively.
    """

    allowed_models: list[str] | None = None
    denied_models: list[str] = []
    budget_limit_usd: float | None = None
    rate_limit_rpm: int | None = None
    allowed_regions: list[str] | None = None
    block_prompt_injection: bool = False
    redact_pii: bool = False

    def allows_model(self, model_name: str) -> bool:
        if model_name in self.denied_models:
            return False
        if self.allowed_models is not None and model_name not in self.allowed_models:
            return False
        return True
