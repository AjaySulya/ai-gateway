import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.models import Policy, PolicyScope
from gateway.policy.merge import merge_policy
from gateway.policy.schemas import EffectivePolicy, PolicyConfig


async def _policies_for_scope(
    db: AsyncSession, scope_type: PolicyScope, scope_id: uuid.UUID
) -> list[Policy]:
    result = await db.execute(
        select(Policy).where(
            Policy.scope_type == scope_type,
            Policy.scope_id == scope_id,
            Policy.enabled.is_(True),
        )
    )
    return list(result.scalars().all())


async def resolve_effective_policy(
    db: AsyncSession,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    project_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
) -> EffectivePolicy:
    """Walks org -> team -> project -> [agent], folding in every enabled
    policy at each level in that order. Order matters: merge_policy only
    ever tightens, so a level can never undo a restriction set above it.
    Multiple policies at the same level are folded in sequence too, using
    the same rule.
    """
    effective = EffectivePolicy()

    levels: list[tuple[PolicyScope, uuid.UUID]] = [
        (PolicyScope.organization, organization_id),
        (PolicyScope.team, team_id),
        (PolicyScope.project, project_id),
    ]
    if agent_id is not None:
        levels.append((PolicyScope.agent, agent_id))

    for scope_type, scope_id in levels:
        for policy in await _policies_for_scope(db, scope_type, scope_id):
            effective = merge_policy(effective, PolicyConfig(**policy.config))

    return effective
