"""Builders that turn database rows into the contract's response objects (shared by several services)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.approval_request import ApprovalRequest
from app.repositories import action_repository
from app.schemas import ActionResponse, ActionSummary, ApprovalResponse


def action_response(action: Action, redact: bool = False) -> ActionResponse:
    """ActionResponse from a row. VIEWERs get the payload redacted (spec section 18); the hash stays visible."""
    data = {name: getattr(action, name) for name in ActionResponse.model_fields if name != "payload_redacted"}
    if redact:
        data["action_payload"] = None
    return ActionResponse.model_validate({**data, "payload_redacted": redact})


def summary_from_row(row) -> ActionSummary:
    action, agent_name, policy_result, final_decision, risk_score, risk_level, approval_status, execution_status = row
    return ActionSummary(
        action_id=action.action_id, agent_id=action.agent_id, agent_name=agent_name, action_type=action.action_type,
        requested_tool_name=action.requested_tool_name, policy_result=policy_result, final_decision=final_decision,
        risk_score=float(risk_score) if risk_score is not None else None, risk_level=risk_level,
        approval_status=approval_status, execution_status=execution_status, trace_id=action.trace_id,
        created_at=action.created_at)


async def action_summary(session: AsyncSession, action_id: uuid.UUID) -> ActionSummary | None:
    rows, _ = await action_repository.list_summaries(
        session, action_id=action_id, agent_id=None, action_type=None, final_decision=None, approval_status=None,
        execution_status=None, risk_level=None, created_from=None, created_to=None, page=1, page_size=1,
        sort_by="created_at", descending=True)
    return summary_from_row(rows[0]) if rows else None


async def approval_response(session: AsyncSession, approval: ApprovalRequest) -> ApprovalResponse:
    """ApprovalResponse with the summary of its action filled in, as the contract examples show."""
    data = {name: getattr(approval, name) for name in ApprovalResponse.model_fields if name != "action_summary"}
    return ApprovalResponse.model_validate({**data, "action_summary": await action_summary(session, approval.action_id)})
