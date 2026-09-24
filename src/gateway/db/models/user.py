from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base
from gateway.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Platform-level bootstrap role: can create organizations. Not tied to any one org -
    # everything else (org_admin, team_lead) is scoped via the membership tables.
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
