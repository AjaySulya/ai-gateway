import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base
from gateway.db.models.mixins import UUIDPrimaryKeyMixin


class UsageStatus(StrEnum):
    success = "success"
    error = "error"


class UsageRecord(UUIDPrimaryKeyMixin, Base):
    """Append-only log of every /v1/chat/completions call, successful or
    not - including calls rejected by policy or budget before a provider
    was ever touched (provider_id is null for those).

    org/team/project/agent ids are denormalized here rather than requiring
    a join through the hierarchy, so budget aggregation ('total spend under
    this org') is a plain SUM(...) WHERE on what's meant to be a
    high-volume table, not a multi-table join on every check.

    No updated_at: rows are never modified after being written, so the
    usual TimestampMixin (which pairs created_at with updated_at) doesn't
    fit - only created_at makes sense for a log.
    """

    __tablename__ = "usage_records"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False
    )
    # Null when no provider ever got a chance: rejected by policy/budget, or
    # the requested model matched no candidate at all.
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )

    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UsageStatus] = mapped_column(
        Enum(UsageStatus, name="usage_status"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Numeric, not Float: this is money - avoid binary floating-point drift
    # across millions of summed rows.
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
