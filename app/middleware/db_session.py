"""Request-scoped transactions.

The middleware commits a successful request before the response is sent.
"""

from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.core.post_commit import discard_jobs, mark_rollback, reset_job_state
from app.db.session import (
    finish_request_transaction,
    get_session_factory,
    reset_current_session,
    set_current_session,
)

logger = get_logger(__name__)

Scope = dict[str, object]
Message = dict[str, object]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class DatabaseSessionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        factory = get_session_factory()
        async with factory() as session:
            token = set_current_session(session)
            reset_job_state()
            response_started = False

            async def send_wrapper(message: Message) -> None:
                nonlocal response_started
                if not response_started and message["type"] == "http.response.start":
                    response_started = True
                    await finish_request_transaction(session)
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
                if not response_started:
                    await session.rollback()
                    discard_jobs()
            except Exception:
                await session.rollback()
                discard_jobs()
                raise
            finally:
                reset_current_session(token)


def mark_failed_request() -> None:
    """Exception handlers call this so the middleware rolls the transaction back."""
    mark_rollback()
    logger.debug("request marked for rollback")
