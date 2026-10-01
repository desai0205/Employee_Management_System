"""Translate exceptions into the public error envelope."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError, ConflictError
from app.core.logging import current_request_id, get_logger
from app.middleware.db_session import mark_failed_request
from app.repositories.errors import raise_for_integrity

logger = get_logger(__name__)


def _body(
    code: str, message: str, details: list[dict[str, str]] | None = None
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": current_request_id(),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        mark_failed_request()
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        mark_failed_request()
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body("validation_error", "Request validation failed.", details),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity(_request: Request, exc: IntegrityError) -> JSONResponse:
        mark_failed_request()
        try:
            raise_for_integrity(exc)
        except ConflictError as conflict:
            return JSONResponse(
                status_code=conflict.status_code,
                content=_body(conflict.code, conflict.message),
            )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        mark_failed_request()
        logger.exception("unhandled_error", error=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_body("internal_error", "An unexpected error occurred."),
        )
