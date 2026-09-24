import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_project_access
from gateway.auth.security import generate_api_key
from gateway.db.models import APIKey, User
from gateway.db.session import get_db
from gateway.schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyRead

router = APIRouter(tags=["api-keys"])


@router.post(
    "/projects/{project_id}/api-keys",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    project_id: uuid.UUID,
    payload: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_project_access),
):
    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        project_id=project_id,
        name=payload.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreated(**APIKeyRead.model_validate(api_key).model_dump(), api_key=raw_key)


@router.get("/projects/{project_id}/api-keys", response_model=list[APIKeyRead])
async def list_api_keys(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(APIKey).where(APIKey.project_id == project_id))
    return result.scalars().all()


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    api_key = await db.get(APIKey, api_key_id)
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")

    await require_project_access(api_key.project_id, user, db)

    api_key.is_active = False
    await db.commit()
