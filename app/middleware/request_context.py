"""Assigns a request id and writes one structured access log per request."""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from app.core.logging import get_logger, reset_request_id, set_request_id

logger = get_logger("http")

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _safe_request_id(raw: str | None) -> str:
    if raw and len(raw) <= 64 and raw.replace("-", "").isalnum():
        return raw
    return str(uuid.uuid4())


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = _safe_request_id(request.headers.get("x-request-id"))
        token = set_request_id(request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status = message["status"]
                if isinstance(status, int):
                    status_code = status
                raw_headers = message["headers"]
                if isinstance(raw_headers, list):
                    headers = MutableHeaders(raw=raw_headers)
                    headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            reset_request_id(token)
