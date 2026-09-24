import uuid

from pydantic import BaseModel, ConfigDict

from gateway.db.models import PolicyScope
from gateway.policy.schemas import PolicyConfig


class PolicyCreate(BaseModel):
    name: str
    scope_type: PolicyScope
    scope_id: uuid.UUID
    config: PolicyConfig
    enabled: bool = True


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    scope_type: PolicyScope
    scope_id: uuid.UUID
    config: PolicyConfig
    enabled: bool
