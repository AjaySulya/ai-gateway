import uuid

from pydantic import BaseModel, ConfigDict


class ModelCreate(BaseModel):
    model_name: str
    display_name: str
    priority: int = 100


class ModelUpdate(BaseModel):
    model_name: str | None = None
    display_name: str | None = None
    priority: int | None = None
    is_active: bool | None = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    model_name: str
    display_name: str
    is_active: bool
    priority: int
