import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base
from gateway.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationRole(StrEnum):
    admin = "admin"
    member = "member"


class TeamRole(StrEnum):
    lead = "lead"
    member = "member"


class OrganizationMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Grants a user a role within an organization. org_admin here implies
    access to everything under the org - teams, projects, agents, policies."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_org_membership_user_org"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name="organization_role"), nullable=False
    )


class TeamMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Grants a user a role within a team. team_lead implies access to
    everything under that team - projects, agents, providers, policies."""

    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_team_membership_user_team"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[TeamRole] = mapped_column(Enum(TeamRole, name="team_role"), nullable=False)
