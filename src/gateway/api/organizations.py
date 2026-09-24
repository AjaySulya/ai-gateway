import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.dependencies import get_current_user, require_superuser
from gateway.db.models import Organization, OrganizationMembership, OrganizationRole, User
from gateway.db.session import get_db
from gateway.schemas.organization import OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    # Org creation is a platform-level (superuser) action, not an org-scoped one -
    # there's no org to check membership against until this call creates one.
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    await db.flush()

    db.add(
        OrganizationMembership(user_id=user.id, organization_id=org.id, role=OrganizationRole.admin)
    )
    await db.commit()
    await db.refresh(org)
    return org


@router.get("", response_model=list[OrganizationRead])
async def list_my_organizations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.is_superuser:
        result = await db.execute(select(Organization))
    else:
        result = await db.execute(
            select(Organization)
            .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == user.id)
        )
    return result.scalars().all()


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = await db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return org
