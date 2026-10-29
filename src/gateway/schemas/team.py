import uuid

from pydantic import BaseModel, ConfigDict


class TeamCreate(BaseModel):
    name: str
    slug: str


class TeamUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
