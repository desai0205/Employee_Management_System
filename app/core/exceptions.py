"""Application errors translated into one HTTP error envelope by the API layer."""


class AppError(Exception):
    """Expected failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=404)


class ForbiddenError(AppError):
    def __init__(
        self, message: str = "You do not have permission to perform this action."
    ) -> None:
        super().__init__("forbidden", message, status_code=403)


class UnauthorizedError(AppError):
    def __init__(
        self,
        code: str = "unauthorized",
        message: str = "Authentication is required.",
    ) -> None:
        super().__init__(code, message, status_code=401)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)
