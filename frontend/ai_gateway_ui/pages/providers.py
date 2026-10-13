import reflex as rx

from ..components import card, data_table, field, page, requires_project
from ..state import PROVIDER_PRESETS, PROVIDER_TYPES, State


def _provider_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["name"]),
        rx.table.cell(rx.code(item["provider_type"])),
        rx.table.cell(rx.code(item["credential_ref"])),
        rx.table.cell(rx.code(item["extra_config"])),
        rx.table.cell(
            rx.cond(
                item["circuit"] == "open",
                rx.badge("Circuit open", color_scheme="red"),
                rx.badge("Healthy", color_scheme="green"),
            )
        ),
    )


def _model_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["provider_name"]),
        rx.table.cell(rx.code(item["model_name"])),
        rx.table.cell(item["display_name"]),
        rx.table.cell(item["priority"]),
    )


def _add_provider() -> rx.Component:
    return card(
        "Add a provider",
        rx.select(
            list(PROVIDER_PRESETS),
            placeholder="Start from a preset",
            on_change=State.apply_preset,
            width="260px",
        ),
        rx.hstack(
            field("Name", rx.input(value=State.prov_name, on_change=State.edit_prov_name, placeholder="groq", width="180px")),
            field(
                "Type",
                rx.select(PROVIDER_TYPES, value=State.prov_type, on_change=State.edit_prov_type, width="180px"),
            ),
            field(
                "Credential variable",
                rx.input(value=State.prov_cred, on_change=State.edit_prov_cred, placeholder="GROQ_API_KEY", width="220px"),
                hint="The name of a variable in the gateway's .env file, never the key itself.",
            ),
            field(
                "API base (optional)",
                rx.input(
                    value=State.prov_api_base,
                    on_change=State.edit_prov_api_base,
                    placeholder="https://api.groq.com/openai/v1",
                    width="340px",
                ),
                hint="Needed for OpenAI-compatible services such as Groq, Gemini, and Ollama.",
            ),
            spacing="3",
            wrap="wrap",
            align="start",
        ),
        rx.button(rx.icon("plus", size=16), "Add provider", on_click=State.create_provider),
        description="Anything OpenAI-compatible uses the openai type plus an API base.",
    )


def _add_model() -> rx.Component:
    return card(
        "Add a model",
        rx.cond(
            State.providers.length() > 0,
            rx.form(
                rx.hstack(
                    field(
                        "Provider",
                        rx.select.root(
                            rx.select.trigger(placeholder="Choose a provider", width="200px"),
                            rx.select.content(
                                rx.foreach(
                                    State.providers,
                                    lambda p: rx.select.item(p["name"], value=p["id"]),
                                )
                            ),
                            value=State.model_provider_id,
                            on_change=State.edit_model_provider_id,
                        ),
                    ),
                    field(
                        "Model name",
                        rx.input(name="model_name", placeholder="llama-3.1-8b-instant", required=True, width="260px"),
                        hint="Exactly as the provider expects it.",
                    ),
                    field("Display name", rx.input(name="display_name", placeholder="Llama 3.1 8B", width="200px")),
                    field(
                        "Priority",
                        rx.input(name="priority", placeholder="100", width="100px"),
                        hint="Lower is tried first.",
                    ),
                    rx.button(rx.icon("plus", size=16), "Add model", type="submit"),
                    spacing="3",
                    wrap="wrap",
                    align="start",
                ),
                on_submit=State.create_model,
                reset_on_submit=True,
                width="100%",
            ),
            rx.text("Add a provider above, then add its models here.", size="2", color_scheme="gray"),
        ),
        description="Register the same model name under two providers with different priorities to get automatic failover.",
    )


def providers_page() -> rx.Component:
    return page(
        "Providers and models",
        "Where requests go, and which models each project can use.",
        requires_project(
            card(
                "Providers",
                data_table(
                    ["Name", "Type", "Credential variable", "Extra config", "Status"],
                    State.providers,
                    _provider_row,
                    "No providers yet. Add one below.",
                ),
            ),
            _add_provider(),
            card(
                "Models",
                data_table(
                    ["Provider", "Model", "Display name", "Priority"],
                    State.models,
                    _model_row,
                    "No models yet. Add one below.",
                ),
            ),
            _add_model(),
        ),
    )
