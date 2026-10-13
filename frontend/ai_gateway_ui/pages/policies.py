import reflex as rx

from ..components import agent_select, card, data_table, field, page, requires_project
from ..state import POLICY_SCOPES, State


def _policy_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["name"]),
        rx.table.cell(rx.code(item["rules"])),
        rx.table.cell(
            rx.cond(
                item["enabled"] == "true",
                rx.badge("Enabled", color_scheme="green"),
                rx.badge("Disabled", color_scheme="gray"),
            )
        ),
        rx.table.cell(
            rx.button(
                rx.icon("trash_2", size=14),
                "Delete",
                size="1",
                variant="soft",
                color_scheme="red",
                on_click=State.delete_policy(item["id"]),
            )
        ),
    )


def _scope_picker() -> rx.Component:
    return card(
        "Where policies apply",
        rx.hstack(
            field(
                "Level",
                rx.select(
                    POLICY_SCOPES,
                    value=State.policy_scope,
                    on_change=State.change_policy_scope,
                    width="200px",
                ),
            ),
            rx.cond(
                State.policy_scope == "agent",
                field("Agent", agent_select()),
            ),
            spacing="4",
            wrap="wrap",
            align="end",
        ),
        rx.text("Showing and creating policies for: ", rx.code(State.policy_scope_label), size="2"),
        description="Organization and team policies come from the selectors at the top of the page.",
    )


def _create_policy() -> rx.Component:
    return card(
        "Create a policy",
        rx.form(
            rx.vstack(
                field("Name", rx.input(name="name", placeholder="chatbot-limits", required=True, width="260px")),
                rx.hstack(
                    field(
                        "Allowed models",
                        rx.input(name="allowed_models", placeholder="llama-3.1-8b-instant, gpt-4o", width="320px"),
                        hint="Comma separated. Anything not listed is blocked.",
                    ),
                    field(
                        "Denied models",
                        rx.input(name="denied_models", placeholder="gpt-3.5-turbo", width="260px"),
                        hint="Comma separated. Always blocked.",
                    ),
                    spacing="3",
                    wrap="wrap",
                    align="start",
                ),
                rx.hstack(
                    field(
                        "Budget (USD)",
                        rx.input(name="budget_limit_usd", placeholder="25", width="140px"),
                        hint="Total spend at this level.",
                    ),
                    field(
                        "Requests per minute",
                        rx.input(name="rate_limit_rpm", placeholder="60", width="160px"),
                    ),
                    spacing="3",
                    wrap="wrap",
                    align="start",
                ),
                rx.hstack(
                    rx.switch(name="block_prompt_injection"),
                    rx.text("Block prompt injection attempts", size="2"),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.switch(name="redact_pii"),
                    rx.text("Redact emails, phone numbers, and card-like numbers", size="2"),
                    spacing="2",
                    align="center",
                ),
                rx.button(rx.icon("plus", size=16), "Create policy", type="submit"),
                spacing="4",
                align="start",
            ),
            on_submit=State.create_policy,
            reset_on_submit=True,
            width="100%",
        ),
        description="Leave a rule blank to skip it. A lower level can tighten what a parent set but never loosen it.",
    )


def policies_page() -> rx.Component:
    return page(
        "Policies",
        "Rules for models, spend, request rate, and content.",
        requires_project(
            _scope_picker(),
            card(
                "Policies at this level",
                data_table(
                    ["Name", "Rules", "Status", ""],
                    State.policies,
                    _policy_row,
                    "No policies at this level yet. Create one below.",
                ),
                description="See the merged result across all levels on the Dashboard.",
            ),
            _create_policy(),
        ),
    )
