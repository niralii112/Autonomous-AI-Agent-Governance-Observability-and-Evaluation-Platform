"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.tool
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    ToolSensitivity,
    ToolStatus,
)


class ToolCreateRequest(BaseModel):
    """Register a tool."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    tool_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=0, max_length=1000)
    tool_sensitivity: ToolSensitivity
    supported_action_type: ActionType


class ToolResponse(BaseModel):
    """Tool record."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    tool_id: UUID
    tool_name: str
    description: str | None
    tool_sensitivity: ToolSensitivity
    supported_action_type: ActionType
    tool_status: ToolStatus
    created_at: datetime
    updated_at: datetime


class ToolResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[ToolResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class ToolUpdateRequest(BaseModel):
    """Patch a tool."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    description: str | None = Field(default=None, min_length=0, max_length=1000)
    tool_status: ToolStatus | None = Field(default=None)
