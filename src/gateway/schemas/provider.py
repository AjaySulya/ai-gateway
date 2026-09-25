import uuid

from pydantic import BaseModel, ConfigDict

from gateway.db.models import ProviderType


class ProviderCreate(BaseModel):
    name: str
    provider_type: ProviderType
    credential_ref: str
    extra_config: dict = {}


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    provider_type: ProviderType
    credential_ref: str
    extra_config: dict
    is_active: bool


class ProviderHealth(BaseModel):
    circuit_open: bool
    failures: int
    opened_until: float | None = None
