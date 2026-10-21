"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.agent
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AgentCategory,
    AgentStatus,
)


class AgentCreateRequest(BaseModel):
    """Register an agent."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_name: str = Field(..., min_length=3, max_length=100)
    agent_category: AgentCategory
    description: str | None = Field(default=None, min_length=0, max_length=1000)
    trust_tier: int = Field(default=2, ge=1, le=3)
    owner_user_id: UUID | None = Field(default=None)


class AgentResponse(BaseModel):
    """Agent record."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    agent_name: str
    agent_category: AgentCategory
    description: str | None
    agent_status: AgentStatus
    trust_tier: int
    owner_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AgentResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[AgentResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class AgentUpdateRequest(BaseModel):
    """Patch an agent."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    description: str | None = Field(default=None, min_length=0, max_length=1000)
    agent_status: AgentStatus | None = Field(default=None)
    trust_tier: int | None = Field(default=None, ge=1, le=3)


class ToolPermissionItem(BaseModel):
    """One permission entry."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    tool_id: UUID
    is_allowed: bool


class ToolPermissionResponse(BaseModel):
    """Stored permission."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    permission_id: UUID
    agent_id: UUID
    tool_id: UUID
    tool_name: str
    is_allowed: bool
    created_at: datetime


class ToolPermissionListResponse(BaseModel):
    """All permissions of an agent (not paginated)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    permissions: list[ToolPermissionResponse]


class ToolPermissionsUpdateRequest(BaseModel):
    """Replace the permission set of an agent."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    permissions: list[ToolPermissionItem]
