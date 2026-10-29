import uuid

from pydantic import BaseModel, ConfigDict

from gateway.db.models import ProviderType


class ProviderCreate(BaseModel):
    name: str
    provider_type: ProviderType
    credential_ref: str
    extra_config: dict = {}


class ProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: ProviderType | None = None
    credential_ref: str | None = None
    extra_config: dict | None = None
    is_active: bool | None = None


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
