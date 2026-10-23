import uuid

import pytest

from app.core.enums import (
    ActionType, ApprovalStatus, ErrorCode, ExecutionStatus, GovernanceDecision, UserRole,
)
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas import ActionSubmissionRequest, ActionSubmissionResponse, ActorContext
from app.services import action_service_stub as stub

AGENT = uuid.uuid4()


@pytest.fixture(autouse=True)
def clean():
    stub.reset_stub()
    yield
    stub.reset_stub()


def actor(role=UserRole.OPERATOR):
    return ActorContext(user_id=uuid.uuid4(), username="op", role=role)


def req(action_type, payload, key="k1", tool="some_tool", agent=AGENT):
    return ActionSubmissionRequest(agent_id=agent, tool_name=tool, action_type=action_type,
                                   action_payload=payload, idempotency_key=key)


def pay(amount, payee="payee-0001"):
    return {"payee_id": payee, "amount": amount, "currency": "USD", "reference": "inv-1"}


async def submit(request, who=None):
    return await stub.submit_action(None, request, who or actor())


# --- the decision follows the seed policies -----------------------------------------------------

@pytest.mark.parametrize("action_type,payload,expected", [
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(450), GovernanceDecision.ALLOW),
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(1000), GovernanceDecision.ALLOW),
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(1000.01), GovernanceDecision.HUMAN_REVIEW),
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(50000), GovernanceDecision.HUMAN_REVIEW),
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(50000.01), GovernanceDecision.BLOCK),
    (ActionType.FINANCE_PROPOSE_PAYMENT, pay(10, "payee-blocked-001"), GovernanceDecision.BLOCK),
    (ActionType.SUPPORT_PROPOSE_REFUND, {"ticket_id": "T-1", "amount": 100, "currency": "USD", "reason": "late"}, GovernanceDecision.ALLOW),
    (ActionType.SUPPORT_PROPOSE_REFUND, {"ticket_id": "T-1", "amount": 100.5, "currency": "USD", "reason": "late"}, GovernanceDecision.HUMAN_REVIEW),
    (ActionType.SUPPORT_ACCESS_CUSTOMER_INFO, {"customer_id": "c-1", "fields": ["email"], "purpose": "help"}, GovernanceDecision.HUMAN_REVIEW),
    (ActionType.FINANCE_ACCESS_SENSITIVE_RECORDS, {"record_set": "payroll", "purpose": "audit"}, GovernanceDecision.HUMAN_REVIEW),
    (ActionType.FINANCE_GET_REPORT, {"report_id": "rpt-001"}, GovernanceDecision.ALLOW),
    (ActionType.FINANCE_GET_REPORT, {"report_id": "rpt-restricted-001"}, GovernanceDecision.BLOCK),
    (ActionType.SUPPORT_GET_TICKET, {"ticket_id": "T-9"}, GovernanceDecision.ALLOW),
])
def test_decide_mirrors_seed_policies(action_type, payload, expected):
    assert stub.decide(action_type, payload) == expected


# --- the response is a valid contract object and tells a consistent story -----------------------------

async def test_allow_runs_the_tool():
    r = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)))
    assert isinstance(r, ActionSubmissionResponse)
    assert r.governance_decision.final_decision == GovernanceDecision.ALLOW
    assert r.execution.execution_status == ExecutionStatus.SUCCEEDED
    assert r.approval is None and r.duplicate is False


async def test_review_creates_a_pending_approval_and_no_execution():
    r = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(25000)))
    assert r.governance_decision.final_decision == GovernanceDecision.HUMAN_REVIEW
    assert r.approval.approval_status == ApprovalStatus.PENDING and r.execution is None


async def test_block_records_a_blocked_execution():
    r = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(60000)))
    assert r.governance_decision.final_decision == GovernanceDecision.BLOCK
    assert r.execution.execution_status == ExecutionStatus.BLOCKED and r.approval is None


@pytest.mark.parametrize("amount", [450, 25000, 60000])
async def test_all_ids_and_hashes_line_up(amount):
    request = req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(amount), key="id-check", tool="payment_processor_sim")
    r = await submit(request)
    assert r.action.agent_id == AGENT and r.action.requested_tool_name == "payment_processor_sim"
    assert r.action.action_type == ActionType.FINANCE_PROPOSE_PAYMENT
    assert r.action.action_payload == request.action_payload
    assert r.action.idempotency_key == "id-check"
    assert r.action.payload_hash == compute_payload_hash(request.action_payload)
    aid = r.action.action_id
    assert r.risk_assessment.action_id == aid and r.governance_decision.action_id == aid
    assert r.governance_decision.risk_assessment_id == r.risk_assessment.risk_assessment_id
    assert r.governance_decision.payload_hash == r.action.payload_hash
    if r.approval:
        assert r.approval.action_id == aid
        assert r.approval.governance_decision_id == r.governance_decision.governance_decision_id
    if r.execution:
        assert r.execution.action_id == aid
        assert r.execution.governance_decision_id == r.governance_decision.governance_decision_id


async def test_submitter_is_recorded():
    who = actor()
    r = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)), who)
    assert r.action.submitted_by_user_id == who.user_id


async def test_each_submission_gets_new_ids():
    a = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450), key="a"))
    b = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450), key="b"))
    assert a.action.action_id != b.action.action_id


# --- idempotency -------------------------------------------------------------------------------------------

async def test_same_key_and_payload_returns_the_same_action_marked_duplicate():
    request = req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450))
    first, second = await submit(request), await submit(request)
    assert first.duplicate is False and second.duplicate is True
    assert second.action.action_id == first.action.action_id


async def test_same_key_with_different_payload_conflicts():
    await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)))
    with pytest.raises(AppError) as e:
        await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(451)))
    assert e.value.error_code == ErrorCode.IDEMPOTENCY_KEY_CONFLICT and e.value.http_status == 409


async def test_same_key_for_a_different_agent_is_independent():
    await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)))
    other = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(451), agent=uuid.uuid4()))
    assert other.duplicate is False


# --- validation and permissions --------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [{}, {"payee_id": "p", "amount": -5, "currency": "USD", "reference": "r"},
                                 {"payee_id": "p", "amount": 5, "currency": "US", "reference": "r"},
                                 {**pay(5), "extra": 1}])
async def test_invalid_payload_is_rejected(bad):
    with pytest.raises(AppError) as e:
        await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, bad))
    assert e.value.error_code == ErrorCode.INVALID_ACTION_PAYLOAD and e.value.http_status == 422


@pytest.mark.parametrize("role", [UserRole.REVIEWER, UserRole.VIEWER])
async def test_only_admin_and_operator_may_submit(role):
    with pytest.raises(AppError) as e:
        await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)), actor(role))
    assert e.value.error_code == ErrorCode.AUTH_INSUFFICIENT_ROLE


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.OPERATOR])
async def test_admin_and_operator_may_submit(role):
    assert (await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)), actor(role))).action


# --- test helpers for Student 2 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("forced", list(GovernanceDecision))
async def test_forcing_a_decision(forced):
    stub.set_stub_decision(forced)
    r = await submit(req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450)))
    assert r.governance_decision.final_decision == forced


async def test_reset_clears_forced_decision_and_idempotency_memory():
    stub.set_stub_decision(GovernanceDecision.BLOCK)
    request = req(ActionType.FINANCE_PROPOSE_PAYMENT, pay(450))
    await submit(request)
    stub.reset_stub()
    again = await submit(request)
    assert again.duplicate is False and again.governance_decision.final_decision == GovernanceDecision.ALLOW
