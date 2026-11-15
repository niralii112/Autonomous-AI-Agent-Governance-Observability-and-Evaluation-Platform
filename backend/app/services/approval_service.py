"""Approvals (spec 12.8 to 12.10, 13.6): create, approve, reject, cancel, and expire.

Each function commits its own transactions, because an approval must be saved BEFORE the tool runs
(the tool runs in execution_service with no database connection held), and because a refusal that is
audited (expired, wrong role, self-approval) must keep its audit row even though an error is raised.

Order of checks in approve_action / reject_action:
  1. the caller's role (ADMIN or REVIEWER)      -> 403 AUTH_INSUFFICIENT_ROLE   (audited)
  2. the approval exists, row-locked            -> 404 RESOURCE_NOT_FOUND
  3. it is still PENDING                        -> 409 APPROVAL_NOT_PENDING
  4. it has not expired (EXPIRED is saved)      -> 409 APPROVAL_EXPIRED         (audited)
  5. the reviewer did not submit the action     -> 403 SELF_APPROVAL_FORBIDDEN  (audited)
"""

import uuid
from datetime import datetime, timedelta, timezone

from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.enums import (
    ActorType, ApprovalStatus, AuditEventName, AuditOutcome, ErrorCode, ExecutionStatus, UserRole,
)
from app.core.exceptions import AppError, NotFoundError
from app.core.trace_context import current_trace_id
from app.models.approval_request import ApprovalRequest
from app.models.execution import Execution
from app.repositories import action_repository, approval_repository, execution_repository
from app.schemas import (
    ActorContext, ApprovalDecisionResponse, ApprovalRejectRequest, ApprovalReviewRequest, AuditEventCreate,
    ExecutionResponse,
)
from app.services import execution_service
from app.services.action_views import approval_response
from app.services.audit_service import record_audit_event

_tracer = trace.get_tracer("governance.approval")
REVIEW_ROLES = (UserRole.ADMIN, UserRole.REVIEWER)
CANCEL_ROLES = (UserRole.ADMIN, UserRole.OPERATOR)


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


# ----------------------------------------------------------------------------------- helpers

async def _audit(session: AsyncSession, event: AuditEventName, approval_id: uuid.UUID, action_id: uuid.UUID | None,
                 outcome: AuditOutcome, data: dict, actor: ActorContext | None = None) -> None:
    await record_audit_event(session, AuditEventCreate(
        event_name=event, actor_type=ActorType.USER if actor else ActorType.SYSTEM,
        actor_user_id=actor.user_id if actor else None, action_id=action_id, entity_type="approval",
        entity_id=approval_id, outcome=outcome, event_data=data))


async def _refuse_role(session: AsyncSession, approval_id: uuid.UUID, actor: ActorContext, attempted: str) -> None:
    """Audit a caller whose role may not do this, save that audit row, then raise 403."""
    approval = await approval_repository.get_by_id(session, approval_id)
    await _audit(session, AuditEventName.APPROVAL_DENIED_UNAUTHORIZED, approval_id,
                 approval.action_id if approval else None, AuditOutcome.DENIED,
                 {"attempted": attempted, "reason": "role", "role": actor.role.value}, actor)
    await session.commit()
    raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")


async def _lock_pending(session: AsyncSession, approval_id: uuid.UUID) -> ApprovalRequest:
    """Row-lock the approval and make sure it is PENDING and not past its expiry (lazy expiry: EXPIRED is saved)."""
    approval = await approval_repository.get_locked(session, approval_id)
    if approval is None:
        raise NotFoundError("Approval not found.")
    if approval.approval_status != ApprovalStatus.PENDING.value:
        raise AppError(ErrorCode.APPROVAL_NOT_PENDING, "This approval has already been decided or has ended.",
                       {"approval_status": approval.approval_status})
    if approval.expires_at <= datetime.now(timezone.utc):
        approval.approval_status = ApprovalStatus.EXPIRED.value
        await _audit(session, AuditEventName.APPROVAL_EXPIRED, approval.approval_id, approval.action_id,
                     AuditOutcome.SUCCESS, {"expires_at": approval.expires_at.isoformat(), "found_by": "review"})
        await session.commit()  # the EXPIRED status must survive the error below
        raise AppError(ErrorCode.APPROVAL_EXPIRED, "This approval has expired.",
                       {"expires_at": approval.expires_at.isoformat()})
    return approval


async def _refuse_self_review(session: AsyncSession, approval: ApprovalRequest, actor: ActorContext,
                              attempted: str) -> None:
    """The person who submitted the action may not review it. A null submitter (an in-process agent) conflicts with nobody."""
    action = await action_repository.get_by_id(session, approval.action_id)
    if action is not None and action.submitted_by_user_id is not None and action.submitted_by_user_id == actor.user_id:
        await _audit(session, AuditEventName.APPROVAL_DENIED_UNAUTHORIZED, approval.approval_id, approval.action_id,
                     AuditOutcome.DENIED, {"attempted": attempted, "reason": "self_approval"}, actor)
        await session.commit()  # the approval stays PENDING; only the audit row is kept
        raise AppError(ErrorCode.SELF_APPROVAL_FORBIDDEN, "You cannot review an action you submitted yourself.")


def _factory_for(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(session.bind, expire_on_commit=False) if session.bind is not None else get_session_factory()


# ----------------------------------------------------------------------------------- approve / reject / cancel

async def approve_action(session: AsyncSession, approval_id: uuid.UUID, request: ApprovalReviewRequest,
                         actor: ActorContext) -> ApprovalDecisionResponse:
    """Approve a held action, then run it (spec 12.9). Repeating the call raises APPROVAL_NOT_PENDING: it never runs twice."""
    with _tracer.start_as_current_span("approval.review") as span:
        span.set_attribute("approval.decision", "APPROVE")
        if actor.role not in REVIEW_ROLES:
            await _refuse_role(session, approval_id, actor, "approve")
        approval = await _lock_pending(session, approval_id)
        await _refuse_self_review(session, approval, actor, "approve")

        now = datetime.now(timezone.utc)
        approval.approval_status = ApprovalStatus.APPROVED.value
        approval.reviewed_by_user_id = actor.user_id
        approval.reviewed_at = now
        approval.review_comment = request.review_comment
        latest = await execution_repository.latest_for_action(session, approval.action_id)
        execution = Execution(
            action_id=approval.action_id, governance_decision_id=approval.governance_decision_id,
            approval_id=approval.approval_id, attempt_number=latest.attempt_number + 1 if latest else 1,
            execution_status=ExecutionStatus.PENDING.value, trace_id=current_trace_id())
        session.add(execution)
        await session.flush()
        await _audit(session, AuditEventName.APPROVAL_APPROVED, approval.approval_id, approval.action_id,
                     AuditOutcome.SUCCESS, {"execution_id": str(execution.execution_id),
                                            "has_comment": bool(request.review_comment)}, actor)
        approval_id, execution_id = approval.approval_id, execution.execution_id
        await session.commit()  # the approval is saved before the tool runs

        # The tool runs through execution_service only. It revalidates everything again (payload, agent, tool,
        # permission, fresh policy, approval) and consumes the approval; a failed check gives a BLOCKED execution.
        await execution_service.execute_controlled_action(_factory_for(session), execution_id)

        session.expunge_all()  # the execution changed in other sessions: read fresh rows
        approval = await approval_repository.get_by_id(session, approval_id)
        execution = await execution_repository.get_by_id(session, execution_id)
        response = ApprovalDecisionResponse(
            approval=await approval_response(session, approval), execution=ExecutionResponse.model_validate(execution))
        await session.commit()
        span.set_attribute("execution.status", response.execution.execution_status.value)
        return response


async def reject_action(session: AsyncSession, approval_id: uuid.UUID, request: ApprovalRejectRequest,
                        actor: ActorContext) -> ApprovalDecisionResponse:
    """Reject a held action (spec 12.10). The action is never executed and no execution row is made."""
    with _tracer.start_as_current_span("approval.review") as span:
        span.set_attribute("approval.decision", "REJECT")
        if actor.role not in REVIEW_ROLES:
            await _refuse_role(session, approval_id, actor, "reject")
        approval = await _lock_pending(session, approval_id)
        await _refuse_self_review(session, approval, actor, "reject")

        approval.approval_status = ApprovalStatus.REJECTED.value
        approval.reviewed_by_user_id = actor.user_id
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.review_comment = request.review_comment
        await _audit(session, AuditEventName.APPROVAL_REJECTED, approval.approval_id, approval.action_id,
                     AuditOutcome.SUCCESS, {"has_comment": True}, actor)
        approval_id = approval.approval_id
        await session.commit()
        session.expunge_all()
        approval = await approval_repository.get_by_id(session, approval_id)
        response = ApprovalDecisionResponse(approval=await approval_response(session, approval), execution=None)
        await session.commit()
        return response


async def cancel_approval(session: AsyncSession, approval_id: uuid.UUID, actor: ActorContext
                          ) -> ApprovalDecisionResponse:
    """Withdraw a PENDING approval (APR-05). ADMIN or OPERATOR. An approval past its expiry is saved as EXPIRED
    and reported as not pending, since it can no longer be cancelled."""
    with _tracer.start_as_current_span("approval.cancel"):
        if actor.role not in CANCEL_ROLES:
            await _refuse_role(session, approval_id, actor, "cancel")
        approval = await approval_repository.get_locked(session, approval_id)
        if approval is None:
            raise NotFoundError("Approval not found.")
        if approval.approval_status == ApprovalStatus.PENDING.value and approval.expires_at <= datetime.now(timezone.utc):
            approval.approval_status = ApprovalStatus.EXPIRED.value
            await _audit(session, AuditEventName.APPROVAL_EXPIRED, approval.approval_id, approval.action_id,
                         AuditOutcome.SUCCESS, {"expires_at": approval.expires_at.isoformat(), "found_by": "cancel"})
            await session.commit()
            raise AppError(ErrorCode.APPROVAL_NOT_PENDING, "This approval has already ended.",
                           {"approval_status": ApprovalStatus.EXPIRED.value})
        if approval.approval_status != ApprovalStatus.PENDING.value:
            raise AppError(ErrorCode.APPROVAL_NOT_PENDING, "This approval has already been decided or has ended.",
                           {"approval_status": approval.approval_status})
        approval.approval_status = ApprovalStatus.CANCELLED.value
        await _audit(session, AuditEventName.APPROVAL_CANCELLED, approval.approval_id, approval.action_id,
                     AuditOutcome.SUCCESS, {}, actor)
        approval_id = approval.approval_id
        await session.commit()
        session.expunge_all()
        approval = await approval_repository.get_by_id(session, approval_id)
        response = ApprovalDecisionResponse(approval=await approval_response(session, approval), execution=None)
        await session.commit()
        return response
