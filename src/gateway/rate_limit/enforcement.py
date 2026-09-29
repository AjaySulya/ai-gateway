import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.data_plane.context import RequestContext
from gateway.db.models import Policy, PolicyScope
from gateway.policy.schemas import PolicyConfig
from gateway.rate_limit.limiter import check_and_increment, get_current_count


def _levels(
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    project_id: uuid.UUID,
    agent_id: uuid.UUID | None,
) -> list[tuple[PolicyScope, uuid.UUID, str]]:
    levels: list[tuple[PolicyScope, uuid.UUID, str]] = [
        (PolicyScope.organization, organization_id, "organization"),
        (PolicyScope.team, team_id, "team"),
        (PolicyScope.project, project_id, "project"),
    ]
    if agent_id is not None:
        levels.append((PolicyScope.agent, agent_id, "agent"))
    return levels


async def check_rate_limit(
    db: AsyncSession, context: RequestContext
) -> tuple[bool, str | None, int | None, int | None]:
    """Checks each hierarchy level's own configured rate_limit_rpm against
    that level's own request count in the current one-minute window -
    same reasoning as usage/budgets.py's per-level check, and for the same
    reason: a single merged EffectivePolicy.rate_limit_rpm can't tell you
    which scope's own counter to check it against (an org-wide 1000 rpm cap
    and a project-only 50 rpm cap merge to "50," but checking a project's
    own count against 50 while never checking the org's own count against
    1000 misses what the org policy was actually for).

    Returns (rate_limited, scope_name, limit_rpm, current_count) - the last
    three are None when rate_limited is False. First level whose own limit
    is exceeded wins; later levels aren't checked (and don't have their
    counters incremented) for that request.
    """
    for scope_type, scope_id, label in _levels(
        context.organization_id, context.team_id, context.project_id, context.agent_id
    ):
        result = await db.execute(
            select(Policy).where(
                Policy.scope_type == scope_type,
                Policy.scope_id == scope_id,
                Policy.enabled.is_(True),
            )
        )
        for policy in result.scalars().all():
            config = PolicyConfig(**policy.config)
            if config.rate_limit_rpm is None:
                continue
            allowed, count = await check_and_increment(label, scope_id, config.rate_limit_rpm)
            if not allowed:
                return True, label, config.rate_limit_rpm, count

    return False, None, None, None


async def get_rate_limit_status(
    db: AsyncSession,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    project_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
) -> list[dict]:
    """Read-only equivalent of check_rate_limit, for the debug endpoint -
    shows every level that has a configured rate_limit_rpm and its current
    count, without incrementing anything."""
    statuses: list[dict] = []
    for scope_type, scope_id, label in _levels(organization_id, team_id, project_id, agent_id):
        result = await db.execute(
            select(Policy).where(
                Policy.scope_type == scope_type,
                Policy.scope_id == scope_id,
                Policy.enabled.is_(True),
            )
        )
        for policy in result.scalars().all():
            config = PolicyConfig(**policy.config)
            if config.rate_limit_rpm is None:
                continue
            count = await get_current_count(label, scope_id)
            statuses.append(
                {"scope": label, "limit_rpm": config.rate_limit_rpm, "current_count": count}
            )
    return statuses
