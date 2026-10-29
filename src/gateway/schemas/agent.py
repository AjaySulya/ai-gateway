import uuid

from pydantic import BaseModel, ConfigDict


class AgentCreate(BaseModel):
    name: str
    slug: str


class AgentUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    slug: str
