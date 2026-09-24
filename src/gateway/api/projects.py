import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_project_access, require_team_access
from gateway.db.models import Agent, Project, Team, User
from gateway.db.session import get_db
from gateway.policy.resolution import resolve_effective_policy
from gateway.policy.schemas import EffectivePolicy
from gateway.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(tags=["projects"])


@router.post(
    "/teams/{team_id}/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED
)
async def create_project(
    team_id: uuid.UUID,
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_team_access),
):
    project = Project(team_id=team_id, name=payload.name, slug=payload.slug)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/teams/{team_id}/projects", response_model=list[ProjectRead])
async def list_projects(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.team_id == team_id))
    return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("/projects/{project_id}/effective-policy", response_model=EffectivePolicy)
async def get_effective_policy(
    project_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_project_access),
):
    """Debug/verification endpoint for Phase 3 - shows exactly what
    /v1/chat/completions computes internally before checking a model against
    it, without needing a live API key or a provider call to see it."""
    project = await db.get(Project, project_id)
    team = await db.get(Team, project.team_id)

    if agent_id is not None:
        agent = await db.get(Agent, agent_id)
        if agent is None or agent.project_id != project_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "agent_id does not belong to this project"
            )

    return await resolve_effective_policy(db, team.organization_id, team.id, project_id, agent_id)
