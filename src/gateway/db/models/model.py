import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gateway.db.base import Base
from gateway.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

from gateway.db.models.provider import Provider


class Model(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "models"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    # The identifier LiteLLM / the provider expects, e.g. "claude-sonnet-4-6", "gpt-4o".
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Lower = preferred. Used by the static fallback router before Jev is layered in.
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    provider: Mapped["Provider"] = relationship(back_populates="models")
