"""Layout and small building blocks shared by every page."""

import reflex as rx

from .state import State

NAV_ITEMS = [
    ("Dashboard", "/", "layout_dashboard"),
    ("Workspace", "/workspace", "folder"),
    ("Providers and models", "/providers", "server"),
    ("Policies", "/policies", "shield"),
    ("API keys", "/api-keys", "key"),
    ("Playground", "/playground", "message_square"),
]


def _nav_row(label: str, icon: str, background) -> rx.Component:
    return rx.hstack(
        rx.icon(icon, size=18),
        rx.text(label, size="3", weight="medium"),
        spacing="3",
        align="center",
        width="100%",
        padding="8px 12px",
        border_radius="6px",
        background=background,
        _hover={"background": rx.color("accent", 3)},
    )


def _nav_item(label: str, href: str, icon: str) -> rx.Component:
    return rx.link(
        rx.cond(
            State.router.page.path == href,
            _nav_row(label, icon, rx.color("accent", 4)),
            _nav_row(label, icon, "transparent"),
        ),
        href=href,
        underline="none",
        width="100%",
    )


def sidebar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("layers", size=22, color=rx.color("accent", 9)),
            rx.heading("AI Gateway", size="5"),
            align="center",
            spacing="2",
            padding="4px 12px 16px 12px",
        ),
        *[_nav_item(*item) for item in NAV_ITEMS],
        rx.spacer(),
        rx.divider(),
        rx.text(State.user_email, size="2", color_scheme="gray", padding_x="12px"),
        rx.button(
            rx.icon("log_out", size=16),
            "Sign out",
            variant="soft",
            color_scheme="gray",
            on_click=State.logout,
            width="100%",
        ),
        width="240px",
        min_width="240px",
        height="100vh",
        padding="16px",
        position="sticky",
        top="0",
        border_right=f"1px solid {rx.color('gray', 5)}",
        spacing="1",
        align="start",
    )


def _selector(items, value, on_change, placeholder: str, label: str) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color_scheme="gray"),
        rx.select.root(
            rx.select.trigger(placeholder=placeholder, width="220px"),
            rx.select.content(
                rx.foreach(items, lambda item: rx.select.item(item["name"], value=item["id"]))
            ),
            value=value,
            on_change=on_change,
        ),
        spacing="1",
        align="start",
    )


def context_bar() -> rx.Component:
    return rx.hstack(
        _selector(State.orgs, State.selected_org_id, State.select_org, "No organization", "Organization"),
        _selector(State.teams, State.selected_team_id, State.select_team, "No team", "Team"),
        _selector(State.projects, State.selected_project_id, State.select_project, "No project", "Project"),
        spacing="4",
        wrap="wrap",
        width="100%",
    )


def agent_select() -> rx.Component:
    return rx.select.root(
        rx.select.trigger(width="220px"),
        rx.select.content(
            rx.select.item("No agent", value="none"),
            rx.foreach(State.agents, lambda agent: rx.select.item(agent["name"], value=agent["id"])),
        ),
        value=State.selected_agent_id,
        on_change=State.select_agent,
    )


def page(title: str, subtitle: str, *children, show_context: bool = True) -> rx.Component:
    header = [
        rx.vstack(
            rx.heading(title, size="7"),
            rx.text(subtitle, size="3", color_scheme="gray"),
            spacing="1",
            align="start",
        )
    ]
    if show_context:
        header.append(context_bar())
    return rx.cond(
        State.logged_in,
        rx.hstack(
            sidebar(),
            rx.box(
                rx.vstack(
                    *header,
                    *children,
                    spacing="5",
                    align="start",
                    width="100%",
                    max_width="1100px",
                ),
                padding="32px",
                flex="1",
                min_width="0",
            ),
            spacing="0",
            align="start",
            width="100%",
            min_height="100vh",
        ),
        rx.center(
            rx.vstack(rx.spinner(), rx.text("Checking your session..."), align="center"),
            height="100vh",
        ),
    )


def requires_project(*children) -> rx.Component:
    return rx.cond(
        State.has_project,
        rx.vstack(*children, spacing="5", align="start", width="100%"),
        rx.callout(
            "Choose a project above to continue. To create one, go to Workspace.",
            icon="info",
            width="100%",
        ),
    )


def card(title: str, *children, description: str = "") -> rx.Component:
    header = [rx.heading(title, size="4")]
    if description:
        header.append(rx.text(description, size="2", color_scheme="gray"))
    return rx.card(
        rx.vstack(
            rx.vstack(*header, spacing="1", align="start"),
            *children,
            spacing="4",
            align="start",
            width="100%",
        ),
        width="100%",
        size="3",
    )


def field(label: str, control: rx.Component, hint: str = "") -> rx.Component:
    parts = [rx.text(label, size="2", weight="medium"), control]
    if hint:
        parts.append(rx.text(hint, size="1", color_scheme="gray"))
    return rx.vstack(*parts, spacing="1", align="start")


def data_table(headers: list[str], rows, row_fn, empty_text: str) -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        rx.table.root(
            rx.table.header(rx.table.row(*[rx.table.column_header_cell(h) for h in headers])),
            rx.table.body(rx.foreach(rows, row_fn)),
            variant="surface",
            width="100%",
        ),
        rx.text(empty_text, size="2", color_scheme="gray"),
    )


def active_badge(flag, on_label: str = "Active", off_label: str = "Inactive") -> rx.Component:
    return rx.cond(
        flag == "true",
        rx.badge(on_label, color_scheme="green"),
        rx.badge(off_label, color_scheme="gray"),
    )
