"""Request Analyzer - structural input validation, run before the Security
Engine's content checks (see chat.py for why that order is deliberately
reversed from the architecture diagram's literal box order). Doesn't
inspect what a message *means* - that's content_filter.py's job; this only
checks shape and size, cheaply, before anything more expensive runs.
"""

from fastapi import HTTPException, status

MAX_MESSAGES = 100
MAX_MESSAGE_CHARS = 50_000
MAX_TOTAL_CHARS = 200_000


def analyze_request(messages: list[dict]) -> None:
    """Raises HTTPException(400) on a structurally invalid or abusive
    request; returns None otherwise."""
    if not messages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "messages must not be empty")

    if len(messages) > MAX_MESSAGES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"too many messages ({len(messages)} > {MAX_MESSAGES})"
        )

    total_chars = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        if len(content) > MAX_MESSAGE_CHARS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"a message exceeds the maximum length ({MAX_MESSAGE_CHARS} chars)",
            )
        total_chars += len(content)

    if total_chars > MAX_TOTAL_CHARS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"total message content exceeds the maximum ({MAX_TOTAL_CHARS} chars)",
        )
