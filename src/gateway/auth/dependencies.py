import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.security import decode_access_token
from gateway.db.models import (
    Agent,
    OrganizationMembership,
    OrganizationRole,
    PolicyScope,
    Project,
    Provider,
    Team,
    TeamMembership,
    TeamRole,
    User,
)
from gateway.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = await db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_error
    return user


async def require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Superuser privileges required")
    return user


async def _org_role(
    db: AsyncSession, user: User, organization_id: uuid.UUID
) -> OrganizationRole | None:
    if user.is_superuser:
        return OrganizationRole.admin
    result = await db.execute(
        select(OrganizationMembership.role).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def _team_role(db: AsyncSession, user: User, team_id: uuid.UUID) -> TeamRole | None:
    result = await db.execute(
        select(TeamMembership.role).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == team_id,
        )
    )
    return result.scalar_one_or_none()


async def require_org_admin(
    organization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    role = await _org_role(db, user, organization_id)
    if role != OrganizationRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organization admin privileges required")
    return user


async def require_team_access(
    team_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Org admin of the team's org, or the team's lead, may manage the team."""
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    if await _org_role(db, user, team.organization_id) == OrganizationRole.admin:
        return user
    if await _team_role(db, user, team_id) == TeamRole.lead:
        return user

    raise HTTPException(
        status.HTTP_403_FORBIDDEN, "Team lead or organization admin privileges required"
    )


async def require_project_access(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolves project -> team -> org; org admin or the owning team's lead may manage it."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    team = await db.get(Team, project.team_id)
    if await _org_role(db, user, team.organization_id) == OrganizationRole.admin:
        return user
    if await _team_role(db, user, team.id) == TeamRole.lead:
        return user

    raise HTTPException(
        status.HTTP_403_FORBIDDEN, "Team lead or organization admin privileges required"
    )


async def require_agent_access(
    agent_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return await require_project_access(agent.project_id, user, db)


async def require_provider_access(
    provider_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    return await require_project_access(provider.project_id, user, db)


async def check_scope_access(
    db: AsyncSession, user: User, scope_type: PolicyScope, scope_id: uuid.UUID
) -> None:
    """Used by the policies router, where the scope (and therefore the access
    check) is a field on the request body rather than a fixed path param."""
    if scope_type == PolicyScope.organization:
        if await _org_role(db, user, scope_id) != OrganizationRole.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Organization admin privileges required")
    elif scope_type == PolicyScope.team:
        await require_team_access(scope_id, user, db)
    elif scope_type == PolicyScope.project:
        await require_project_access(scope_id, user, db)
    elif scope_type == PolicyScope.agent:
        await require_agent_access(scope_id, user, db)
