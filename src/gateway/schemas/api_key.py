import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class APIKeyCreate(BaseModel):
    name: str


class APIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None


class APIKeyCreated(APIKeyRead):
    """Returned once, at creation time, with the raw key. Never persisted or
    retrievable again after this response."""

    api_key: str
