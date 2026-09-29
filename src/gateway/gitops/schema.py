"""Pydantic models for the versioned config files under config/.
Validated before anything touches the Control API - a schema error in CI
means no sync job runs and no request reaches the gateway.
"""

from pydantic import BaseModel, ConfigDict, field_validator

from gateway.db.models import ProviderType
from gateway.policy.schemas import PolicyConfig


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    display_name: str
    priority: int = 100


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider_type: ProviderType
    credential_ref: str
    extra_config: dict = {}
    models: list[ModelConfig] = []


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str


class PolicyConfigEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scope: str  # "project" | "agent:<slug>"
    config: PolicyConfig


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    providers: list[ProviderConfig] = []
    agents: list[AgentConfig] = []
    policies: list[PolicyConfigEntry] = []


class TeamConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    projects: list[ProjectConfig] = []
    policies: list[PolicyConfigEntry] = []


class OrgConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    teams: list[TeamConfig] = []
    policies: list[PolicyConfigEntry] = []

    @field_validator("slug")
    @classmethod
    def slug_no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError(f"slug must not contain spaces: '{v}'")
        return v


class GatewayConfig(BaseModel):
    """Top-level wrapper for a config file. A file can declare one or more
    organizations. Most repos will have one file per org or one per team."""

    model_config = ConfigDict(extra="forbid")

    organizations: list[OrgConfig] = []
