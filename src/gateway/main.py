from contextlib import asynccontextmanager

from fastapi import FastAPI

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AI Gateway", version="0.1.0", lifespan=lifespan)

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
