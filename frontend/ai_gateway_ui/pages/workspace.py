import reflex as rx

from ..components import card, data_table, field, page
from ..state import State


def _name_slug_row(item) -> rx.Component:
    return rx.table.row(rx.table.cell(item["name"]), rx.table.cell(rx.code(item["slug"])))


def _create_form(button_label: str, on_submit, name_placeholder: str) -> rx.Component:
    return rx.form(
        rx.hstack(
            field("Name", rx.input(name="name", placeholder=name_placeholder, required=True, width="220px")),
            field(
                "Slug",
                rx.input(name="slug", placeholder="Made from the name if blank", width="220px"),
            ),
            rx.button(rx.icon("plus", size=16), button_label, type="submit"),
            spacing="3",
            align="end",
            wrap="wrap",
        ),
        on_submit=on_submit,
        reset_on_submit=True,
        width="100%",
    )


def _needs(selected, message: str, content: rx.Component) -> rx.Component:
    return rx.cond(selected != "", content, rx.text(message, size="2", color_scheme="gray"))


def workspace_page() -> rx.Component:
    return page(
        "Workspace",
        "Organizations contain teams, teams contain projects, and projects contain agents.",
        card(
            "Organizations",
            data_table(["Name", "Slug"], State.orgs, _name_slug_row, "No organizations yet. Create the first one below."),
            _create_form("Create organization", State.create_org, "Acme"),
            description="Creating an organization needs a superuser account.",
        ),
        card(
            "Teams",
            data_table(["Name", "Slug"], State.teams, _name_slug_row, "No teams in this organization yet."),
            _needs(
                State.selected_org_id,
                "Choose or create an organization first.",
                _create_form("Create team", State.create_team, "Platform"),
            ),
        ),
        card(
            "Projects",
            data_table(["Name", "Slug"], State.projects, _name_slug_row, "No projects in this team yet."),
            _needs(
                State.selected_team_id,
                "Choose or create a team first.",
                _create_form("Create project", State.create_project, "Support chatbot"),
            ),
            description="Each project has its own providers, models, API keys, and usage.",
        ),
        card(
            "Agents",
            data_table(["Name", "Slug"], State.agents, _name_slug_row, "No agents in this project yet."),
            _needs(
                State.selected_project_id,
                "Choose or create a project first.",
                _create_form("Create agent", State.create_agent, "Refund assistant"),
            ),
            description="Optional. Send an X-Agent-Id header to attribute requests to an agent and apply agent-level policies.",
        ),
    )
