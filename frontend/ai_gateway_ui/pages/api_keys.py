import reflex as rx

from ..components import active_badge, card, data_table, field, page, requires_project
from ..state import State


def _revoke_dialog(item) -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("trash_2", size=14),
                "Revoke key",
                size="1",
                variant="soft",
                color_scheme="red",
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Revoke this key?"),
            rx.alert_dialog.description(
                "Anything using it stops working right away. A revoked key can't be turned back on."
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Keep key", variant="soft", color_scheme="gray")),
                rx.alert_dialog.action(
                    rx.button(
                        "Revoke key",
                        color_scheme="red",
                        on_click=State.revoke_api_key(item["id"]),
                    )
                ),
                spacing="3",
                margin_top="16px",
                justify="end",
            ),
        ),
    )


def _key_row(item) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item["name"]),
        rx.table.cell(rx.code(item["key_prefix"])),
        rx.table.cell(item["last_used"]),
        rx.table.cell(active_badge(item["is_active"], "Active", "Revoked")),
        rx.table.cell(
            rx.cond(item["is_active"] == "true", _revoke_dialog(item), rx.fragment())
        ),
    )


def _new_key_banner() -> rx.Component:
    return rx.cond(
        State.new_api_key != "",
        rx.callout.root(
            rx.callout.icon(rx.icon("key")),
            rx.callout.text(
                "Copy this key now. It is shown once and can't be retrieved later.",
            ),
            color_scheme="amber",
            width="100%",
        ),
    )


def _new_key_value() -> rx.Component:
    return rx.cond(
        State.new_api_key != "",
        rx.hstack(
            rx.code(State.new_api_key, size="3"),
            rx.button(
                rx.icon("copy", size=14),
                "Copy key",
                size="1",
                variant="soft",
                on_click=rx.set_clipboard(State.new_api_key),
            ),
            rx.button("Done", size="1", variant="soft", color_scheme="gray", on_click=State.dismiss_new_key),
            spacing="3",
            align="center",
            wrap="wrap",
        ),
    )


def api_keys_page() -> rx.Component:
    return page(
        "API keys",
        "Keys your applications use to call /v1/chat/completions for this project.",
        requires_project(
            card(
                "Issue a key",
                rx.form(
                    rx.hstack(
                        field("Name", rx.input(name="name", placeholder="local-dev", required=True, width="260px")),
                        rx.button(rx.icon("plus", size=16), "Issue key", type="submit"),
                        spacing="3",
                        align="end",
                        wrap="wrap",
                    ),
                    on_submit=State.issue_api_key,
                    reset_on_submit=True,
                    width="100%",
                ),
                _new_key_banner(),
                _new_key_value(),
                description="These are different from your sign-in. Keys only work on the data plane.",
            ),
            card(
                "Keys for this project",
                data_table(
                    ["Name", "Starts with", "Last used", "Status", ""],
                    State.api_keys,
                    _key_row,
                    "No keys yet. Issue one above.",
                ),
            ),
        ),
    )
