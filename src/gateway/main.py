from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from gateway.api import (
    agents,
    api_keys,
    auth,
    chat,
    health,
    organizations,
    policies,
    projects,
    providers,
    teams,
)
from gateway.observability.otel import configure_observability, shutdown_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_observability()
    yield
    shutdown_observability()


app = FastAPI(title="AI Gateway", version="0.1.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(providers.router)
app.include_router(policies.router)
app.include_router(api_keys.router)
app.include_router(chat.router)
