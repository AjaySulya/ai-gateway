import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import check_scope_access, get_current_user
from gateway.db.models import Policy, PolicyScope, User
from gateway.db.session import get_db
from gateway.schemas.policy import PolicyCreate, PolicyRead

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Scope is a field on the body, not the path, so the access check happens
    # here rather than as a route dependency.
    await check_scope_access(db, user, payload.scope_type, payload.scope_id)

    policy = Policy(**payload.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("", response_model=list[PolicyRead])
async def list_policies(
    scope_type: PolicyScope,
    scope_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Policy).where(Policy.scope_type == scope_type, Policy.scope_id == scope_id)
    )
    return result.scalars().all()


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    policy = await db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    await check_scope_access(db, user, policy.scope_type, policy.scope_id)

    await db.delete(policy)
    await db.commit()
