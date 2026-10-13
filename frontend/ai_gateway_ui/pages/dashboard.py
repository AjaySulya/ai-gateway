import reflex as rx

from ..components import card, data_table, page, requires_project
from ..state import State


def _figure(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", color_scheme="gray"),
        rx.heading(value, size="6", weight="medium"),
        spacing="1",
        align="start",
    )


def _limit_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["scope"]),
        rx.table.cell(item["limit_rpm"]),
        rx.table.cell(item["current_count"]),
    )


def _health_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["name"]),
        rx.table.cell(rx.code(item["provider_type"])),
        rx.table.cell(
            rx.cond(
                item["circuit"] == "open",
                rx.badge("Circuit open", color_scheme="red"),
                rx.badge("Healthy", color_scheme="green"),
            )
        ),
        rx.table.cell(item["failures"]),
    )


def dashboard_page() -> rx.Component:
    return page(
        "Dashboard",
        "Usage, policy, and provider health for the selected project.",
        requires_project(
            rx.button(
                rx.icon("refresh_cw", size=16),
                "Refresh",
                variant="soft",
                on_click=State.reload_data,
            ),
            card(
                "Usage so far",
                rx.grid(
                    _figure("Requests", State.usage_total),
                    _figure("Succeeded", State.usage_success),
                    _figure("Failed", State.usage_error),
                    _figure("Cost (USD)", State.usage_cost_text),
                    _figure("Input tokens", State.usage_in_tokens),
                    _figure("Output tokens", State.usage_out_tokens),
                    columns="3",
                    spacing="5",
                    width="100%",
                ),
                rx.vstack(
                    rx.hstack(
                        rx.text("Success rate", size="2", color_scheme="gray"),
                        rx.spacer(),
                        rx.text(State.success_rate_text, size="2"),
                        width="100%",
                    ),
                    rx.progress(value=State.success_rate, max=100, width="100%"),
                    spacing="2",
                    width="100%",
                ),
                description="Cost counts only models LiteLLM has pricing for. Streaming requests don't record cost.",
            ),
            card(
                "Provider health",
                data_table(
                    ["Provider", "Type", "Status", "Recent failures"],
                    State.providers,
                    _health_row,
                    "No providers yet. Add one on the Providers and models page.",
                ),
                description="A provider's circuit opens after five failures in a row and retries after 30 seconds.",
            ),
            card(
                "Rate limits right now",
                data_table(
                    ["Level", "Limit per minute", "Used this minute"],
                    State.rate_limits,
                    _limit_row,
                    "No rate limits set. Add one on the Policies page.",
                ),
            ),
            card(
                "Effective policy",
                rx.code_block(State.effective_policy_json, language="json", width="100%"),
                description="Policies from organization, team, project, and agent merged. A lower level can only tighten what a parent set.",
            ),
        ),
    )
