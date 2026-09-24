import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_project_access
from gateway.db.models import Agent, User
from gateway.db.session import get_db
from gateway.schemas.agent import AgentCreate, AgentRead

router = APIRouter(tags=["agents"])


@router.post(
    "/projects/{project_id}/agents", response_model=AgentRead, status_code=status.HTTP_201_CREATED
)
async def create_agent(
    project_id: uuid.UUID,
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_project_access),
):
    agent = Agent(project_id=project_id, name=payload.name, slug=payload.slug)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/projects/{project_id}/agents", response_model=list[AgentRead])
async def list_agents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.project_id == project_id))
    return result.scalars().all()
