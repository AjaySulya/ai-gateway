import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_org_admin
from gateway.db.models import Team, TeamMembership, TeamRole, User
from gateway.db.session import get_db
from gateway.schemas.team import TeamCreate, TeamRead

router = APIRouter(tags=["teams"])


@router.post(
    "/organizations/{organization_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    organization_id: uuid.UUID,
    payload: TeamCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_org_admin),
):
    team = Team(organization_id=organization_id, name=payload.name, slug=payload.slug)
    db.add(team)
    await db.flush()

    # Org admins already have implicit access via the org membership check, so
    # only give an explicit team membership row to a non-superuser creator.
    if not user.is_superuser:
        db.add(TeamMembership(user_id=user.id, team_id=team.id, role=TeamRole.lead))
    await db.commit()
    await db.refresh(team)
    return team


@router.get("/organizations/{organization_id}/teams", response_model=list[TeamRead])
async def list_teams(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Team).where(Team.organization_id == organization_id))
    return result.scalars().all()


@router.get("/teams/{team_id}", response_model=TeamRead)
async def get_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return team
