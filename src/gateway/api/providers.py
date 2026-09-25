import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_project_access, require_provider_access
from gateway.db.models import Model, Provider, User
from gateway.db.session import get_db
from gateway.routing import circuit_breaker
from gateway.schemas.model_catalog import ModelCreate, ModelRead
from gateway.schemas.provider import ProviderCreate, ProviderHealth, ProviderRead

router = APIRouter(tags=["providers"])


@router.post(
    "/projects/{project_id}/providers",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    project_id: uuid.UUID,
    payload: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_project_access),
):
    provider = Provider(project_id=project_id, **payload.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("/projects/{project_id}/providers", response_model=list[ProviderRead])
async def list_providers(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Provider).where(Provider.project_id == project_id))
    return result.scalars().all()


@router.post(
    "/providers/{provider_id}/models",
    response_model=ModelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_model(
    provider_id: uuid.UUID,
    payload: ModelCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_provider_access),
):
    model = Model(provider_id=provider_id, **payload.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/providers/{provider_id}/models", response_model=list[ModelRead])
async def list_models(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Model).where(Model.provider_id == provider_id))
    return result.scalars().all()


@router.get("/providers/{provider_id}/health", response_model=ProviderHealth)
async def get_provider_health(
    provider_id: uuid.UUID,
    user: User = Depends(require_provider_access),
):
    """Circuit-breaker state for Phase 4's router - not a live probe, just
    what the last few real requests through this provider have shown."""
    return await circuit_breaker.get_state(provider_id)
