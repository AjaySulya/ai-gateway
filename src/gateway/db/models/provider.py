import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gateway.db.base import Base
from gateway.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProviderType(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    azure_openai = "azure_openai"
    bedrock = "bedrock"
    vertex_ai = "vertex_ai"
    huggingface = "huggingface"
    other = "other"


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "providers"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type"), nullable=False
    )
    # Points to a secret in a vault/secrets manager. Raw credentials are never stored here.
    credential_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    # Provider-specific extras the LiteLLM call needs beyond api_key - e.g.
    # api_base for a dedicated HuggingFace Inference Endpoint, or api_version
    # for Azure OpenAI. Kept generic so a new provider quirk never needs a
    # new column.
    extra_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="providers")
    models: Mapped[list["Model"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )
