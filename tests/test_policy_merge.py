from gateway.policy.merge import merge_policy
from gateway.policy.schemas import EffectivePolicy, PolicyConfig


def test_root_is_unrestricted():
    root = EffectivePolicy()
    assert root.allows_model("anything") is True


def test_child_cannot_loosen_parent_allowlist():
    org = merge_policy(EffectivePolicy(), PolicyConfig(allowed_models=["gpt-4o", "claude-sonnet-4-6"]))
    # Team tries to allow a model the org never permitted - must not appear.
    team = merge_policy(org, PolicyConfig(allowed_models=["gpt-4o", "gpt-3.5-turbo"]))
    assert team.allowed_models == ["gpt-4o"]


def test_child_can_narrow_allowlist():
    org = merge_policy(EffectivePolicy(), PolicyConfig(allowed_models=["gpt-4o", "claude-sonnet-4-6"]))
    project = merge_policy(org, PolicyConfig(allowed_models=["claude-sonnet-4-6"]))
    assert project.allowed_models == ["claude-sonnet-4-6"]


def test_unset_override_inherits_parent_allowlist():
    org = merge_policy(EffectivePolicy(), PolicyConfig(allowed_models=["gpt-4o"]))
    team = merge_policy(org, PolicyConfig())  # team sets no policy at all
    assert team.allowed_models == ["gpt-4o"]


def test_denylist_is_a_union_and_cannot_be_removed_downstream():
    org = merge_policy(EffectivePolicy(), PolicyConfig(denied_models=["llama-2-7b"]))
    project = merge_policy(org, PolicyConfig(denied_models=["gpt-3.5-turbo"]))
    assert set(project.denied_models) == {"llama-2-7b", "gpt-3.5-turbo"}


def test_denylist_beats_allowlist_even_at_the_same_level():
    policy = merge_policy(
        EffectivePolicy(), PolicyConfig(allowed_models=["gpt-4o"], denied_models=["gpt-4o"])
    )
    assert policy.allows_model("gpt-4o") is False


def test_budget_only_ever_tightens():
    org = merge_policy(EffectivePolicy(), PolicyConfig(budget_limit_usd=1000))
    # Team tries to raise its own budget above the org cap - must not work.
    team = merge_policy(org, PolicyConfig(budget_limit_usd=5000))
    assert team.budget_limit_usd == 1000

    project = merge_policy(team, PolicyConfig(budget_limit_usd=200))
    assert project.budget_limit_usd == 200


def test_budget_unset_inherits_parent_cap():
    org = merge_policy(EffectivePolicy(), PolicyConfig(budget_limit_usd=1000))
    team = merge_policy(org, PolicyConfig())
    assert team.budget_limit_usd == 1000


def test_rate_limit_only_ever_tightens():
    org = merge_policy(EffectivePolicy(), PolicyConfig(rate_limit_rpm=100))
    team = merge_policy(org, PolicyConfig(rate_limit_rpm=500))
    assert team.rate_limit_rpm == 100


def test_regions_intersect_like_allowed_models():
    org = merge_policy(EffectivePolicy(), PolicyConfig(allowed_regions=["us-east-1", "eu-west-1"]))
    project = merge_policy(org, PolicyConfig(allowed_regions=["eu-west-1", "ap-south-1"]))
    assert project.allowed_regions == ["eu-west-1"]


def test_allows_model_respects_final_allowlist():
    policy = merge_policy(EffectivePolicy(), PolicyConfig(allowed_models=["gpt-4o"]))
    assert policy.allows_model("gpt-4o") is True
    assert policy.allows_model("claude-sonnet-4-6") is False


def test_full_hierarchy_walk_only_narrows():
    """Simulates org -> team -> project -> agent without a DB: each level
    can restrict further, and nothing set by a parent ever reappears."""
    effective = EffectivePolicy()
    effective = merge_policy(effective, PolicyConfig(denied_models=["gpt-3.5-turbo"], budget_limit_usd=10_000))
    effective = merge_policy(effective, PolicyConfig(budget_limit_usd=2_000))
    effective = merge_policy(
        effective, PolicyConfig(allowed_models=["gpt-4o", "claude-sonnet-4-6"], budget_limit_usd=5_000)
    )
    effective = merge_policy(effective, PolicyConfig(allowed_models=["claude-sonnet-4-6"]))

    assert effective.allowed_models == ["claude-sonnet-4-6"]
    assert effective.denied_models == ["gpt-3.5-turbo"]
    assert effective.budget_limit_usd == 2_000  # tightest cap set anywhere in the chain
    assert effective.allows_model("claude-sonnet-4-6") is True
    assert effective.allows_model("gpt-4o") is False  # narrowed out at the agent level
    assert effective.allows_model("gpt-3.5-turbo") is False  # denied at the org level
