"""Phase 5 - usage tracking and budget enforcement.

- tracker.py    writes a UsageRecord for every /v1/chat/completions call
                (success, provider failure, policy denial, or budget
                denial), plus token/cost extraction for non-streaming
                responses via litellm.completion_cost()
- budgets.py    checks each hierarchy level's own budget_limit_usd against
                that level's own cumulative spend - see budgets.py's
                docstring for why this can't just reuse Phase 3's merged
                EffectivePolicy.budget_limit_usd

Cumulative, all-time budgets only - no daily/monthly reset window yet.
rate_limit_rpm is still unenforced; that's Phase 6.
"""

