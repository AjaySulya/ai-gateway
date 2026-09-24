from gateway.policy.schemas import EffectivePolicy, PolicyConfig


def merge_policy(base: EffectivePolicy, override: PolicyConfig) -> EffectivePolicy:
    """Folds one more policy into an accumulating effective policy.

    Every tightening guarantee in the system rests on this function: it
    must never be able to produce a result looser than `base`, regardless
    of what `override` asks for.
    """
    if override.allowed_models is not None:
        allowed_models = (
            list(override.allowed_models)
            if base.allowed_models is None
            else [m for m in base.allowed_models if m in override.allowed_models]
        )
    else:
        allowed_models = base.allowed_models

    denied_models = sorted(set(base.denied_models) | set(override.denied_models or []))

    budget_limit_usd = _tighter_min(base.budget_limit_usd, override.budget_limit_usd)
    rate_limit_rpm = _tighter_min(base.rate_limit_rpm, override.rate_limit_rpm)

    if override.allowed_regions is not None:
        allowed_regions = (
            list(override.allowed_regions)
            if base.allowed_regions is None
            else [r for r in base.allowed_regions if r in override.allowed_regions]
        )
    else:
        allowed_regions = base.allowed_regions

    return EffectivePolicy(
        allowed_models=allowed_models,
        denied_models=denied_models,
        budget_limit_usd=budget_limit_usd,
        rate_limit_rpm=rate_limit_rpm,
        allowed_regions=allowed_regions,
    )


def _tighter_min(a: float | None, b: float | None) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
