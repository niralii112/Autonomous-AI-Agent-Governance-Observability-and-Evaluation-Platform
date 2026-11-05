"""Approvals. This step adds request_human_approval; approve, reject, cancel and expiry come next."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ActorType, AuditEventName, AuditOutcome
from app.models.approval_request import ApprovalRequest
from app.schemas import AuditEventCreate
from app.services.audit_service import record_audit_event


async def request_human_approval(
    session: AsyncSession, *, action_id: uuid.UUID, agent_id: uuid.UUID, governance_decision_id: uuid.UUID,
    payload_hash: str,
) -> ApprovalRequest:
    """Create the PENDING approval for a HUMAN_REVIEW decision. It expires after APPROVAL_TTL_SECONDS.
    The caller's transaction commits it."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=get_settings().approval_ttl_seconds)
    approval = ApprovalRequest(action_id=action_id, governance_decision_id=governance_decision_id,
                               payload_hash=payload_hash, expires_at=expires_at)
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    await record_audit_event(session, AuditEventCreate(
        event_name=AuditEventName.APPROVAL_REQUESTED, actor_type=ActorType.SYSTEM, agent_id=agent_id,
        action_id=action_id, entity_type="approval", entity_id=approval.approval_id, outcome=AuditOutcome.SUCCESS,
        event_data={"governance_decision_id": str(governance_decision_id), "expires_at": expires_at.isoformat()}))
    return approval
