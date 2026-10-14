import os
import reflex as rx

config = rx.Config(
    app_name="ai_gateway_ui",
    api_url=os.getenv(
        "GATEWAY_URL",
        "http://localhost:8000",
    ),
    backend_port=int(os.getenv("PORT", "8080")),
)   

