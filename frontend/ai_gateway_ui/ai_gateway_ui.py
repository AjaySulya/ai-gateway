"""Reflex admin console for the AI Gateway - app setup and routes."""

import reflex as rx

from .pages.api_keys import api_keys_page
from .pages.dashboard import dashboard_page
from .pages.login import login_page
from .pages.playground import playground_page
from .pages.policies import policies_page
from .pages.providers import providers_page
from .pages.workspace import workspace_page
from .state import State

app = rx.App(
    # Cyan keeps the accent clear of the green/amber/red used for status badges.
    theme=rx.theme(accent_color="cyan", gray_color="slate", radius="small"),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap"
    ],
    style={"font_family": "'IBM Plex Sans', system-ui, sans-serif"},
)

app.add_page(
    login_page, route="/login", title="Sign in - AI Gateway", on_load=State.login_page_load
)
app.add_page(dashboard_page, route="/", title="Dashboard - AI Gateway", on_load=State.init_page)
app.add_page(
    workspace_page, route="/workspace", title="Workspace - AI Gateway", on_load=State.init_page
)
app.add_page(
    providers_page,
    route="/providers",
    title="Providers and models - AI Gateway",
    on_load=State.init_page,
)
app.add_page(
    policies_page, route="/policies", title="Policies - AI Gateway", on_load=State.init_page
)
app.add_page(
    api_keys_page, route="/api-keys", title="API keys - AI Gateway", on_load=State.init_page
)
app.add_page(
    playground_page,
    route="/playground",
    title="Playground - AI Gateway",
    on_load=State.init_page,
)
