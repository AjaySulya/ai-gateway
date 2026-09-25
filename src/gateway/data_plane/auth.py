import uuid
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.security import hash_api_key
from gateway.data_plane.context import RequestContext
from gateway.db.models import Agent, APIKey, Project, Team
from gateway.db.session import get_db


async def resolve_api_key(
    authorization: str = Header(..., description="Bearer <api key>"),
    x_agent_id: uuid.UUID | None = Header(default=None, alias="X-Agent-Id"),
    db: AsyncSession = Depends(get_db),
) -> RequestContext:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Expected 'Authorization: Bearer <api key>'"
        )
    raw_key = authorization.removeprefix("Bearer ").strip()

    result = await db.execute(select(APIKey).where(APIKey.key_hash == hash_api_key(raw_key)))
    api_key = result.scalar_one_or_none()
    if api_key is None or not api_key.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    project = await db.get(Project, api_key.project_id)
    team = await db.get(Team, project.team_id)

    agent_id = None
    if x_agent_id is not None:
        agent = await db.get(Agent, x_agent_id)
        if agent is None or agent.project_id != project.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "X-Agent-Id does not belong to this project"
            )
        agent_id = agent.id

    api_key.last_used_at = datetime.now(UTC)
    await db.commit()

    return RequestContext(
        request_id=uuid.uuid4(),
        organization_id=team.organization_id,
        team_id=team.id,
        project_id=project.id,
        api_key_id=api_key.id,
        agent_id=agent_id,
    )
