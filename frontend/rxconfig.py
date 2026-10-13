import reflex as rx

config = rx.Config(
    app_name="ai_gateway_ui",
    frontend_port=3000,
    # The gateway itself listens on 8000, so Reflex's own backend moves to 8001.
    backend_port=8000,
    api_url="http://localhost:8000",
)
