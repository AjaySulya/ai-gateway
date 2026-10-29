import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import (
    require_agent_access,
    require_project_access,
    require_project_member,
)
from gateway.db.models import Agent, User
from gateway.db.session import get_db
from gateway.schemas.agent import AgentCreate, AgentRead, AgentUpdate

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


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_agent_access),
):
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/projects/{project_id}/agents", response_model=list[AgentRead])
async def list_agents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_project_member),
):
    result = await db.execute(select(Agent).where(Agent.project_id == project_id))
    return result.scalars().all()
