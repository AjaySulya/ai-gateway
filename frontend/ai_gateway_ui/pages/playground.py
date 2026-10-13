import reflex as rx

from ..components import agent_select, card, field, page, requires_project
from ..state import PLAYGROUND_EXAMPLES, State


def _registered_models() -> rx.Component:
    return rx.cond(
        State.model_names.length() > 0,
        rx.hstack(
            rx.text("Registered:", size="2", color_scheme="gray"),
            rx.foreach(
                State.model_names,
                lambda name: rx.badge(
                    name,
                    variant="soft",
                    cursor="pointer",
                    on_click=State.edit_pg_model(name),
                ),
            ),
            spacing="2",
            wrap="wrap",
            align="center",
        ),
    )


def _request_card() -> rx.Component:
    return card(
        "Request",
        rx.hstack(
            field(
                "Project API key",
                rx.input(
                    value=State.pg_api_key,
                    on_change=State.edit_pg_api_key,
                    type="password",
                    placeholder="sk-proj-...",
                    width="340px",
                ),
                hint="Filled in automatically when you issue a key.",
            ),
            field("Agent (optional)", agent_select()),
            spacing="4",
            wrap="wrap",
            align="start",
        ),
        field(
            "Model",
            rx.input(
                value=State.pg_model,
                on_change=State.edit_pg_model,
                placeholder="llama-3.1-8b-instant",
                width="340px",
            ),
            hint="Type any name. An unregistered or disallowed model shows how the gateway refuses it.",
        ),
        _registered_models(),
        field(
            "System prompt (optional)",
            rx.text_area(value=State.pg_system, on_change=State.edit_pg_system, rows="2", width="100%"),
        ),
        field(
            "Message",
            rx.text_area(value=State.pg_message, on_change=State.edit_pg_message, rows="4", width="100%"),
        ),
        rx.hstack(
            rx.text("Try:", size="2", color_scheme="gray"),
            *[
                rx.button(
                    label,
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=State.use_example(label),
                )
                for label in PLAYGROUND_EXAMPLES
            ],
            spacing="2",
            wrap="wrap",
            align="center",
        ),
        rx.button(
            rx.cond(State.pg_busy, rx.spinner(size="2"), rx.icon("send", size=16)),
            "Send request",
            on_click=State.send_chat,
            disabled=State.pg_busy,
        ),
    )


def _response_card() -> rx.Component:
    return card(
        "Response",
        rx.hstack(
            rx.badge(State.pg_status_text, color_scheme=State.pg_status_color, size="2"),
            rx.text(State.pg_latency_ms, " ms", size="2", color_scheme="gray"),
            rx.cond(
                State.pg_tokens != "",
                rx.text(State.pg_tokens, " tokens", size="2", color_scheme="gray"),
            ),
            rx.cond(
                State.pg_retry_after != "",
                rx.text("Retry after ", State.pg_retry_after, " s", size="2", color_scheme="gray"),
            ),
            spacing="3",
            align="center",
            wrap="wrap",
        ),
        rx.cond(
            State.pg_error_detail != "",
            rx.callout(State.pg_error_detail, icon="info", color_scheme="red", width="100%"),
        ),
        rx.cond(
            State.pg_reply != "",
            rx.box(
                rx.markdown(State.pg_reply),
                padding="12px",
                border_radius="6px",
                background=rx.color("gray", 3),
                width="100%",
            ),
        ),
        rx.text("Raw response", size="2", weight="medium"),
        rx.code_block(State.pg_raw, language="json", width="100%"),
    )


def playground_page() -> rx.Component:
    return page(
        "Playground",
        "Send a real request through the gateway and see exactly what comes back.",
        requires_project(
            _request_card(),
            rx.cond(State.pg_has_result, _response_card()),
        ),
    )
