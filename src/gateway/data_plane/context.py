import uuid
from dataclasses import dataclass


@dataclass
class RequestContext:
    """Carries the resolved identity of a data-plane request through the
    pipeline. Later phases (policy, rate limiting, usage tracking, tracing)
    all consume this rather than re-resolving the API key themselves."""

    request_id: uuid.UUID
    organization_id: uuid.UUID
    team_id: uuid.UUID
    project_id: uuid.UUID
    api_key_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    # Set by the route handler once the request body is parsed - not known
    # at auth time, but part of the context every later stage expects.
    model_requested: str | None = None
