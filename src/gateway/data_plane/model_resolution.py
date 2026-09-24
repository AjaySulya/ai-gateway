import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.models import Model, Provider


async def resolve_model(
    db: AsyncSession, project_id: uuid.UUID, requested_model_name: str
) -> tuple[Model, Provider]:
    """Static, single-candidate resolution for Phase 2 - the requested model
    must match exactly one active Model under an active Provider on this
    project. Multi-candidate selection (Jev, fallback chains) is Phase 4;
    this function's signature is the seam it plugs into."""
    result = await db.execute(
        select(Model, Provider)
        .join(Provider, Model.provider_id == Provider.id)
        .where(
            Provider.project_id == project_id,
            Provider.is_active.is_(True),
            Model.model_name == requested_model_name,
            Model.is_active.is_(True),
        )
        .order_by(Model.priority.asc())
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Model '{requested_model_name}' is not available for this project",
        )
    model, provider = row
    return model, provider
