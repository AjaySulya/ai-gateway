import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base
from gateway.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PolicyScope(StrEnum):
    organization = "organization"
    team = "team"
    project = "project"
    agent = "agent"


class Policy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # scope_id references organizations/teams/projects/agents depending on scope_type.
    # No DB-level FK since the target table is polymorphic - enforced at the application
    # layer (Control API) instead. Effective-policy resolution (Phase 3) queries this
    # table by (scope_type, scope_id) for each level of a request's hierarchy.
    scope_type: Mapped[PolicyScope] = mapped_column(
        Enum(PolicyScope, name="policy_scope"), nullable=False
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Holds allowed_models, denied_models, budget_limit_usd, rate_limit_rpm,
    # allowed_regions, etc. Shape is validated at the application layer.
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
