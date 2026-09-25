import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.context import RequestContext
from gateway.db.models import Policy, PolicyScope, UsageRecord, UsageStatus
from gateway.policy.schemas import PolicyConfig


async def _spend_for_scope(db: AsyncSession, column, scope_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            column == scope_id, UsageRecord.status == UsageStatus.success
        )
    )
    return float(result.scalar_one())


async def check_budget(
    db: AsyncSession, context: RequestContext
) -> tuple[bool, str | None, float | None, float | None]:
    """Checks each level's *own* configured budget_limit_usd against that
    level's *own* cumulative spend - independently, not via the single
    merged EffectivePolicy.budget_limit_usd from Phase 3.

    A merged scalar can't do this correctly: if an org sets a $1000
    org-wide cap and a project under it sets a $200 project cap, the
    tighter number ($200) is what EffectivePolicy resolves to - but
    checking $200 against the org's total spend (or $1000 against just this
    project's spend) doesn't match what either policy actually meant. Each
    cap has to be checked against the total for the scope it was set at.

    Cumulative, all-time - there's no daily/monthly reset window here. A
    period field on PolicyConfig and a time-bounded sum are the natural
    next step, not built in this phase - see README.

    Returns (over_budget, scope_name, cap, spent); the last three are None
    when over_budget is False.
    """
    levels = [
        (
            PolicyScope.organization,
            context.organization_id,
            UsageRecord.organization_id,
            "organization",
        ),
        (PolicyScope.team, context.team_id, UsageRecord.team_id, "team"),
        (PolicyScope.project, context.project_id, UsageRecord.project_id, "project"),
    ]
    if context.agent_id is not None:
        levels.append((PolicyScope.agent, context.agent_id, UsageRecord.agent_id, "agent"))

    for scope_type, scope_id, usage_column, label in levels:
        result = await db.execute(
            select(Policy).where(
                Policy.scope_type == scope_type,
                Policy.scope_id == scope_id,
                Policy.enabled.is_(True),
            )
        )
        for policy in result.scalars().all():
            config = PolicyConfig(**policy.config)
            if config.budget_limit_usd is None:
                continue
            spent = await _spend_for_scope(db, usage_column, scope_id)
            if spent >= config.budget_limit_usd:
                return True, label, config.budget_limit_usd, spent

    return False, None, None, None
