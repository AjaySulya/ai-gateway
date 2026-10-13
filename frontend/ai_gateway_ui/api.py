"""Thin async client for the gateway's Control API and data plane.

This runs server-side inside the Reflex backend process, so the browser never
talks to the gateway directly - no CORS setup is needed on the gateway.
"""

import os
import time
from typing import Any

import httpx

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000").rstrip("/")


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text or resp.reason_phrase
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        if isinstance(detail, list):  # FastAPI validation errors
            parts = []
            for err in detail:
                loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
                parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
            return "; ".join(parts)
        return str(detail)
    return str(body)


def _unreachable() -> ApiError:
    return ApiError(0, f"Can't reach the gateway at {GATEWAY_URL}. Check that it is running.")


async def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: Any = None,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=60.0) as client:
            resp = await client.request(
                method, path, json=json, params=params, data=data, headers=headers
            )
    except httpx.ConnectError as exc:
        raise _unreachable() from exc
    except httpx.TimeoutException as exc:
        raise ApiError(0, "The gateway took too long to respond.") from exc
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, _detail(resp))
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


async def chat(
    api_key: str, payload: dict[str, Any], agent_id: str | None = None
) -> tuple[int, int, Any, dict[str, str]]:
    """Calls /v1/chat/completions and returns (status, latency_ms, body, headers).

    Unlike request(), a 4xx/5xx is returned rather than raised - the playground
    exists to show exactly what the gateway answered, including refusals.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    if agent_id:
        headers["X-Agent-Id"] = agent_id
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=120.0) as client:
            resp = await client.post("/v1/chat/completions", json=payload, headers=headers)
    except httpx.ConnectError as exc:
        raise _unreachable() from exc
    except httpx.TimeoutException as exc:
        raise ApiError(0, "The request timed out after 120 seconds.") from exc
    elapsed_ms = int((time.monotonic() - start) * 1000)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    return (
        resp.status_code,
        elapsed_ms,
        body,
        {k.lower(): v for k, v in resp.headers.items()},
    )
