"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.common
"""

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ErrorCode,
    SortOrder,
    UserRole,
)


class ErrorDetail(BaseModel):
    """One field-level validation problem."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    field: str
    message: str


class ErrorResponse(BaseModel):
    """The single error body used by every non-2xx response."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    error_code: ErrorCode
    error_message: str
    details: list[ErrorDetail] | None
    trace_id: str | None
    timestamp: datetime


class ActorContext(BaseModel):
    """Authenticated caller passed to services."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    user_id: UUID
    username: str
    role: UserRole


class PaginationParams(BaseModel):
    """Parsed pagination query."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=25, ge=1, le=100)
    sort_by: str = Field(default='created_at')
    sort_order: SortOrder = Field(default=SortOrder('desc'))


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic page envelope (spec: Page[T]). The contract's concrete *Page classes have the same shape."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
