"""Department schemas."""

import uuid

from pydantic import Field, field_validator

from app.schemas.common import ORMModel


class DepartmentCreate(ORMModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=32)
    description: str | None = Field(default=None, max_length=2000)
    manager_id: uuid.UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned.replace("-", "").isalnum():
            raise ValueError("Department code must be alphanumeric.")
        return cleaned


class DepartmentUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    manager_id: uuid.UUID | None = None


class DepartmentRead(ORMModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    manager_id: uuid.UUID | None
