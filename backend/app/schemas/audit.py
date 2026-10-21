"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.audit
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActorType,
    AuditEventName,
    AuditOutcome,
)


class AuditEventCreate(BaseModel):
    """Input of record_audit_event."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    event_name: AuditEventName
    actor_type: ActorType
    actor_user_id: UUID | None = Field(default=None)
    agent_id: UUID | None = Field(default=None)
    action_id: UUID | None = Field(default=None)
    entity_type: str | None = Field(default=None)
    entity_id: UUID | None = Field(default=None)
    outcome: AuditOutcome
    event_data: dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    """Stored audit event (append-only)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    audit_event_id: UUID
    event_name: AuditEventName
    actor_type: ActorType
    actor_user_id: UUID | None
    agent_id: UUID | None
    action_id: UUID | None
    entity_type: str | None
    entity_id: UUID | None
    trace_id: str | None
    outcome: AuditOutcome
    event_data: dict[str, Any]
    created_at: datetime


class AuditEventResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[AuditEventResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
