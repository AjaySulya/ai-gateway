import reflex as rx

from ..components import field
from ..state import State

# The order a request really takes through the gateway - a true sequence, so numbering is honest here.
PIPELINE = [
    "Authenticate the project API key",
    "Rate limit",
    "Check policy",
    "Check budget",
    "Validate the request",
    "Scan for injection and personal data",
    "Route to a provider",
    "Retry or fail over",
    "Record usage",
]


def _pipeline_panel() -> rx.Component:
    return rx.vstack(
        rx.heading("One endpoint for every model", size="8"),
        rx.text(
            "Every request passes these checks before a provider sees it.",
            size="3",
            color_scheme="gray",
        ),
        rx.vstack(
            *[
                rx.hstack(
                    rx.text(str(index + 1), size="2", color_scheme="gray", width="20px"),
                    rx.text(step, size="3"),
                    spacing="3",
                    align="baseline",
                )
                for index, step in enumerate(PIPELINE)
            ],
            spacing="2",
            align="start",
            padding_top="16px",
        ),
        spacing="3",
        align="start",
        max_width="420px",
    )


def _sign_in_form() -> rx.Component:
    return rx.form(
        rx.vstack(
            field("Email", rx.input(name="email", type="email", required=True, width="100%")),
            field("Password", rx.input(name="password", type="password", required=True, width="100%")),
            rx.button("Sign in", type="submit", width="100%", size="3"),
            spacing="4",
            align="stretch",
            width="100%",
        ),
        on_submit=State.login,
        width="100%",
    )


def _setup_form() -> rx.Component:
    return rx.form(
        rx.vstack(
            rx.text(
                "Creates the first admin account. This only works while no users exist.",
                size="2",
                color_scheme="gray",
            ),
            field("Your name", rx.input(name="full_name", required=True, width="100%")),
            field("Email", rx.input(name="email", type="email", required=True, width="100%")),
            field("Password", rx.input(name="password", type="password", required=True, width="100%")),
            rx.button("Create admin and sign in", type="submit", width="100%", size="3"),
            spacing="4",
            align="stretch",
            width="100%",
        ),
        on_submit=State.bootstrap_admin,
        width="100%",
    )


def login_page() -> rx.Component:
    return rx.flex(
        rx.box(
            _pipeline_panel(),
            display=["none", "none", "flex"],
            flex="1",
            align_items="center",
            justify_content="center",
            padding="48px",
            background=rx.color("gray", 2),
        ),
        rx.center(
            rx.vstack(
                rx.heading("Sign in", size="6"),
                rx.cond(
                    State.auth_error != "",
                    rx.callout(State.auth_error, icon="info", color_scheme="red", width="100%"),
                ),
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Sign in", value="signin"),
                        rx.tabs.trigger("First-time setup", value="setup"),
                    ),
                    rx.tabs.content(rx.box(_sign_in_form(), padding_top="16px"), value="signin"),
                    rx.tabs.content(rx.box(_setup_form(), padding_top="16px"), value="setup"),
                    default_value="signin",
                    width="100%",
                ),
                spacing="4",
                align="start",
                width="100%",
                max_width="380px",
            ),
            flex="1",
            padding="32px",
        ),
        width="100%",
        min_height="100vh",
    )
