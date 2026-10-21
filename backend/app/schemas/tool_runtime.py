"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.tool_runtime
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    ErrorCode,
)


class ExecutionGrant(BaseModel):
    """HMAC-signed capability required by BaseTool.invoke. Minted only by execution_service."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    execution_id: UUID
    action_id: UUID
    tool_name: str
    payload_hash: str
    expires_at: datetime
    nonce: str
    signature: str


class ToolInvocationRequest(BaseModel):
    """Input of a tool."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    execution_id: UUID
    action_id: UUID
    tool_name: str
    action_type: ActionType
    action_payload: dict[str, Any]


class ToolInvocationResult(BaseModel):
    """Output of a tool."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    success: bool
    output: dict[str, Any]
    error_code: ErrorCode | None = Field(default=None)
    error_message: str | None = Field(default=None)
