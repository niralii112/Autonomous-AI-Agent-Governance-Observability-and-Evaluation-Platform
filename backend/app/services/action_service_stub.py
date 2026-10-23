"""TEMPORARY STAND-IN for app.services.action_service.submit_action (spec: stubs from
contracts/examples while a dependency is unfinished).

This is NOT governance. It returns the contract's example responses, re-stamped with the
ids and payload of the request, so Student 2 can build and test the agent-run flow
(run_agent_scenario) before the real submit_action exists.

Same signature as the real one. When the real service is ready, change ONE import line:
    from app.services.action_service_stub import submit_action   # now
    from app.services.action_service import submit_action        # later

What is realistic:  the decision (ALLOW / HUMAN_REVIEW / BLOCK) follows the seed-policy
                    thresholds, the ids line up, the payload hash is real, idempotency works,
                    the payload is validated, and only ADMIN/OPERATOR may submit.
What is NOT real:   no database, nothing is stored, no policy engine, no risk model, no tool
                    runs, and policy_evaluation / risk_assessment contents are copied from the
                    example files.
"""

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActionType, ErrorCode, GovernanceDecision, UserRole
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas import (
    ACTION_PAYLOAD_MODELS,
    ActionSubmissionRequest,
    ActionSubmissionResponse,
    ActorContext,
)

_EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
_VARIANT_FILES = {
    GovernanceDecision.ALLOW: "ACT-01.response.json",
    GovernanceDecision.HUMAN_REVIEW: "ACT-01.response.human-review.json",
    GovernanceDecision.BLOCK: "ACT-01.response.block.json",
}

# Same facts as the seed policies in contracts/examples/policies/seed-policies.json
_READ_ONLY = {
    ActionType.FINANCE_GET_REPORT, ActionType.FINANCE_GENERATE_SUMMARY,
    ActionType.SUPPORT_GET_TICKET, ActionType.SUPPORT_GENERATE_RESPONSE,
}
_DENYLISTED_PAYEES = {"payee-blocked-001"}
_RESTRICTED_REPORTS = {"rpt-restricted-001"}
_SENSITIVE_RECORD_SETS = {"bank_accounts", "payroll"}

_variants: dict[GovernanceDecision, dict[str, Any]] = {}
_seen: dict[tuple[uuid.UUID, str], tuple[str, dict[str, Any]]] = {}
_forced: GovernanceDecision | None = None


def set_stub_decision(decision: GovernanceDecision | None) -> None:
    """Force every submission to one outcome (or None to go back to the rules). For tests."""
    global _forced
    _forced = decision


def reset_stub() -> None:
    """Forget remembered idempotency keys and any forced decision. For tests."""
    global _forced
    _seen.clear()
    _forced = None


def _variant(decision: GovernanceDecision) -> dict[str, Any]:
    if decision not in _variants:
        _variants[decision] = json.loads((_EXAMPLES / _VARIANT_FILES[decision]).read_text())
    return copy.deepcopy(_variants[decision])


def decide(action_type: ActionType, payload: dict[str, Any]) -> GovernanceDecision:
    """What the seed policies would decide (simplified). Anything unmatched needs review,
    like GOVERNANCE_NO_MATCH_DECISION=HUMAN_REVIEW."""
    amount = payload.get("amount", 0)
    if action_type in _READ_ONLY:
        if action_type == ActionType.FINANCE_GET_REPORT and payload.get("report_id") in _RESTRICTED_REPORTS:
            return GovernanceDecision.BLOCK
        return GovernanceDecision.ALLOW
    if action_type == ActionType.FINANCE_PROPOSE_PAYMENT:
        if payload.get("payee_id") in _DENYLISTED_PAYEES or amount > 50000:
            return GovernanceDecision.BLOCK
        return GovernanceDecision.HUMAN_REVIEW if amount > 1000 else GovernanceDecision.ALLOW
    if action_type == ActionType.SUPPORT_PROPOSE_REFUND:
        return GovernanceDecision.HUMAN_REVIEW if amount > 100 else GovernanceDecision.ALLOW
    # FINANCE_ACCESS_SENSITIVE_RECORDS, SUPPORT_ACCESS_CUSTOMER_INFO and anything else
    return GovernanceDecision.HUMAN_REVIEW


def _build(request: ActionSubmissionRequest, actor: ActorContext, decision: GovernanceDecision) -> dict[str, Any]:
    body = _variant(decision)
    now = datetime.now(timezone.utc).isoformat()
    payload_hash = compute_payload_hash(request.action_payload)
    action_id, decision_id, risk_id = (str(uuid.uuid4()) for _ in range(3))

    action = body["action"]
    action.update(
        action_id=action_id, agent_id=str(request.agent_id), requested_tool_name=request.tool_name,
        action_type=request.action_type.value, action_payload=request.action_payload,
        payload_hash=payload_hash, idempotency_key=request.idempotency_key,
        submitted_by_user_id=str(actor.user_id), created_at=now,
    )
    risk = body["risk_assessment"]
    risk.update(risk_assessment_id=risk_id, action_id=action_id)
    gd = body["governance_decision"]
    gd.update(governance_decision_id=decision_id, action_id=action_id,
              risk_assessment_id=risk_id, payload_hash=payload_hash)
    if body["approval"] is not None:
        approval_id = str(uuid.uuid4())
        body["approval"].update(approval_id=approval_id, action_id=action_id,
                                governance_decision_id=decision_id)
    if body["execution"] is not None:
        body["execution"].update(execution_id=str(uuid.uuid4()), action_id=action_id,
                                 governance_decision_id=decision_id, approval_id=None)
    body["duplicate"] = False
    return body


async def submit_action(
    session: AsyncSession, request: ActionSubmissionRequest, actor: ActorContext
) -> ActionSubmissionResponse:
    """STUB with the real signature. `session` is accepted and ignored."""
    if actor.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")

    try:
        ACTION_PAYLOAD_MODELS[request.action_type].model_validate(request.action_payload)
    except ValidationError as exc:
        details = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        raise AppError(ErrorCode.INVALID_ACTION_PAYLOAD,
                       "action_payload does not match the schema for this action_type.",
                       {d["field"]: d["message"] for d in details}) from None

    key = (request.agent_id, request.idempotency_key)
    payload_hash = compute_payload_hash(request.action_payload)
    if key in _seen:
        stored_hash, stored = _seen[key]
        if stored_hash != payload_hash:
            raise AppError(ErrorCode.IDEMPOTENCY_KEY_CONFLICT,
                           "This idempotency_key was already used with a different payload.")
        again = copy.deepcopy(stored)
        again["duplicate"] = True
        return ActionSubmissionResponse.model_validate(again)

    decision = _forced or decide(request.action_type, request.action_payload)
    body = _build(request, actor, decision)
    response = ActionSubmissionResponse.model_validate(body)
    _seen[key] = (payload_hash, json.loads(response.model_dump_json()))
    return response
