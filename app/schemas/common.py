"""Shared pagination and error response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, str]] = Field(default_factory=list)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class StatusMessage(BaseModel):
    status: str


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
