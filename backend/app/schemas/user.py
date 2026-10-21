"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.user
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    UserRole,
)


class UserCreateRequest(BaseModel):
    """Create a user."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    role: UserRole


class UserResponse(BaseModel):
    """User record (no password fields)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    user_id: UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[UserResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class UserUpdateRequest(BaseModel):
    """Patch a user."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: UserRole | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    password: str | None = Field(default=None, min_length=12, max_length=128)
