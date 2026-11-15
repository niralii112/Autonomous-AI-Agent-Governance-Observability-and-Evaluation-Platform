"""approve_action, reject_action and cancel_approval (spec 12.9, 12.10, APR-05).

Scenarios T-05 (approve), T-06 (reject), T-07 (expired), T-08 (wrong role and self-approval),
T-16 (two reviewers at once), the replay of an approval, and the TOCTOU tamper test of spec 13.6.
The services are called directly; the HTTP router for approvals comes in step 14.
"""

import asyncio
import json
import uuid

import pytest
from pydantic import ValidationError

from app.core.enums import ErrorCode, UserRole
from app.core.exceptions import AppError
from app.schemas import ActorContext, ApprovalRejectRequest, ApprovalReviewRequest
from app.services import approval_service
from tests.integration.api_support import audit_rows, client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import FakeTool, pay_body, risk, session_factory, tools, world  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


def actor_of(make_user, name, role):
    return ActorContext(user_id=make_user(name, role.value), username=name, role=role)


async def held(client, make_user, finance_id, risk, submitter="ops", role="OPERATOR"):
    """Submit a 5000 payment: it is held for a human (T-02). Returns the approval id."""
    h = await headers_for(client, make_user, submitter, role)
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, 5000), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["governance_decision"]["final_decision"] == "HUMAN_REVIEW"
    return uuid.UUID(r.json()["approval"]["approval_id"])


async def approve(session_factory, approval_id, actor, comment="Verified"):
    async with session_factory() as s:
        return await approval_service.approve_action(s, approval_id, ApprovalReviewRequest(review_comment=comment), actor)


async def reject(session_factory, approval_id, actor, comment="Amount mismatch"):
    async with session_factory() as s:
        return await approval_service.reject_action(s, approval_id, ApprovalRejectRequest(review_comment=comment), actor)


async def cancel(session_factory, approval_id, actor):
    async with session_factory() as s:
        return await approval_service.cancel_approval(s, approval_id, actor)


def status_of(db, approval_id):
    return db("SELECT approval_status FROM approval_requests WHERE approval_id=:a", a=approval_id)[0]["approval_status"]


def events(db):
    return [r["event_name"] for r in db("SELECT event_name FROM audit_events ORDER BY created_at, audit_event_id")]


async def raises(coro, code):
    with pytest.raises(AppError) as caught:
        await coro
    assert caught.value.error_code == code, caught.value.error_message
    return caught.value


# ------------------------------------------------------------------------------------------ T-05 approve

async def test_t05_approving_runs_the_action_once(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    reviewer = actor_of(make_user, "rev1", UserRole.REVIEWER)
    assert tools["payment_processor_sim"].calls == []

    result = await approve(session_factory, approval_id, reviewer)

    assert result.approval.approval_status.value == "APPROVED"
    assert result.approval.reviewed_by_user_id == reviewer.user_id and result.approval.review_comment == "Verified"
    assert result.approval.consumed_at is not None and result.approval.action_summary is not None
    assert (result.execution.execution_status.value, result.execution.attempt_number) == ("SUCCEEDED", 1)
    assert result.execution.approval_id == approval_id
    assert len(tools["payment_processor_sim"].calls) == 1
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 1
    assert db("SELECT final_decision FROM governance_decisions")[0]["final_decision"] == "HUMAN_REVIEW"  # unchanged
    names = events(db)
    assert {"APPROVAL_REQUESTED", "APPROVAL_APPROVED", "EXECUTION_STARTED", "EXECUTION_SUCCEEDED"} <= set(names)
    assert names.index("APPROVAL_APPROVED") < names.index("EXECUTION_STARTED")


async def test_an_approval_cannot_be_replayed(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    reviewer = actor_of(make_user, "rev1", UserRole.REVIEWER)
    await approve(session_factory, approval_id, reviewer)
    await raises(approve(session_factory, approval_id, reviewer), ErrorCode.APPROVAL_NOT_PENDING)
    await raises(reject(session_factory, approval_id, reviewer), ErrorCode.APPROVAL_NOT_PENDING)
    assert len(tools["payment_processor_sim"].calls) == 1
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 1


async def test_an_admin_may_approve_and_no_comment_is_needed(client, make_user, finance_id, tools, risk, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    result = await approve(session_factory, approval_id, actor_of(make_user, "boss", UserRole.ADMIN), comment=None)
    assert result.approval.approval_status.value == "APPROVED" and result.approval.review_comment is None


async def test_a_failing_tool_after_approval_is_a_failed_execution_not_an_error(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    tools["payment_processor_sim"].mode = "fail"
    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    assert result.approval.approval_status.value == "APPROVED"
    assert (result.execution.execution_status.value, result.execution.error_code.value) == ("FAILED", "TOOL_EXECUTION_FAILED")


async def test_an_unknown_approval_is_not_found(client, make_user, finance_id, tools, risk, session_factory):
    reviewer = actor_of(make_user, "rev1", UserRole.REVIEWER)
    await raises(approve(session_factory, uuid.uuid4(), reviewer), ErrorCode.RESOURCE_NOT_FOUND)
    await raises(reject(session_factory, uuid.uuid4(), reviewer), ErrorCode.RESOURCE_NOT_FOUND)
    await raises(cancel(session_factory, uuid.uuid4(), actor_of(make_user, "boss", UserRole.ADMIN)), ErrorCode.RESOURCE_NOT_FOUND)


# ------------------------------------------------------------------------------------------ T-06 reject

async def test_t06_rejecting_never_runs_the_action(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    reviewer = actor_of(make_user, "rev1", UserRole.REVIEWER)

    result = await reject(session_factory, approval_id, reviewer, "Amount mismatch")

    assert result.execution is None
    assert (result.approval.approval_status.value, result.approval.review_comment) == ("REJECTED", "Amount mismatch")
    assert result.approval.reviewed_by_user_id == reviewer.user_id and result.approval.consumed_at is None
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 0 and tools["payment_processor_sim"].calls == []
    assert "APPROVAL_REJECTED" in events(db) and "EXECUTION_STARTED" not in events(db)
    assert db("SELECT final_decision FROM governance_decisions")[0]["final_decision"] == "HUMAN_REVIEW"


def test_a_rejection_needs_a_comment():
    with pytest.raises(ValidationError):
        ApprovalRejectRequest(review_comment="")
    with pytest.raises(ValidationError):
        ApprovalRejectRequest()


# ------------------------------------------------------------------------------------------ T-07 expiry

async def test_t07_an_expired_approval_is_marked_expired_and_never_runs(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=approval_id)

    await raises(approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER)), ErrorCode.APPROVAL_EXPIRED)

    assert status_of(db, approval_id) == "EXPIRED"  # saved even though an error was raised
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 0 and tools["payment_processor_sim"].calls == []
    assert "APPROVAL_EXPIRED" in events(db)
    await raises(approve(session_factory, approval_id, actor_of(make_user, "rev2", UserRole.REVIEWER)), ErrorCode.APPROVAL_NOT_PENDING)


async def test_an_expired_approval_cannot_be_rejected_or_cancelled_as_pending(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=approval_id)
    await raises(reject(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER)), ErrorCode.APPROVAL_EXPIRED)
    assert status_of(db, approval_id) == "EXPIRED"
    await raises(cancel(session_factory, approval_id, actor_of(make_user, "boss", UserRole.ADMIN)), ErrorCode.APPROVAL_NOT_PENDING)


async def test_cancelling_an_approval_past_its_expiry_saves_it_as_expired(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=approval_id)
    await raises(cancel(session_factory, approval_id, actor_of(make_user, "boss", UserRole.ADMIN)), ErrorCode.APPROVAL_NOT_PENDING)
    assert status_of(db, approval_id) == "EXPIRED"


# ------------------------------------------------------------------------------------------ T-08 who may review

@pytest.mark.parametrize("role", [UserRole.OPERATOR, UserRole.VIEWER])
async def test_t08_only_admin_and_reviewer_may_review(client, make_user, finance_id, tools, risk, db, session_factory, role):
    approval_id = await held(client, make_user, finance_id, risk)
    outsider = actor_of(make_user, "outsider", role)
    await raises(approve(session_factory, approval_id, outsider), ErrorCode.AUTH_INSUFFICIENT_ROLE)
    await raises(reject(session_factory, approval_id, outsider), ErrorCode.AUTH_INSUFFICIENT_ROLE)
    assert status_of(db, approval_id) == "PENDING" and tools["payment_processor_sim"].calls == []
    assert events(db).count("APPROVAL_DENIED_UNAUTHORIZED") == 2
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 0


async def test_t08_nobody_reviews_their_own_action(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk, submitter="boss", role="ADMIN")
    me = ActorContext(user_id=db("SELECT user_id FROM users WHERE username='boss'")[0]["user_id"], username="boss", role=UserRole.ADMIN)
    await raises(approve(session_factory, approval_id, me), ErrorCode.SELF_APPROVAL_FORBIDDEN)
    await raises(reject(session_factory, approval_id, me), ErrorCode.SELF_APPROVAL_FORBIDDEN)
    assert status_of(db, approval_id) == "PENDING" and tools["payment_processor_sim"].calls == []
    assert events(db).count("APPROVAL_DENIED_UNAUTHORIZED") == 2
    # someone else can still decide it
    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    assert result.execution.execution_status.value == "SUCCEEDED"


async def test_an_action_with_no_recorded_submitter_has_no_self_approval_conflict(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    db("ALTER TABLE actions DISABLE TRIGGER trg_actions_append_only")  # actions are append-only; the test lifts that rule
    try:
        db("UPDATE actions SET submitted_by_user_id = NULL")
    finally:
        db("ALTER TABLE actions ENABLE TRIGGER trg_actions_append_only")
    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    assert result.approval.approval_status.value == "APPROVED"


# ------------------------------------------------------------------------------------------ T-16 concurrency

async def test_t16_two_reviewers_at_once_run_the_action_exactly_once(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    one, two = actor_of(make_user, "rev1", UserRole.REVIEWER), actor_of(make_user, "rev2", UserRole.REVIEWER)

    results = await asyncio.gather(approve(session_factory, approval_id, one), approve(session_factory, approval_id, two),
                                   return_exceptions=True)

    wins = [r for r in results if not isinstance(r, Exception)]
    losses = [r for r in results if isinstance(r, Exception)]
    assert len(wins) == 1 and len(losses) == 1
    assert isinstance(losses[0], AppError) and losses[0].error_code == ErrorCode.APPROVAL_NOT_PENDING
    assert len(tools["payment_processor_sim"].calls) == 1
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 1
    assert status_of(db, approval_id) == "APPROVED"


async def test_an_approve_and_a_reject_at_once_end_with_one_winner(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    one, two = actor_of(make_user, "rev1", UserRole.REVIEWER), actor_of(make_user, "rev2", UserRole.REVIEWER)
    results = await asyncio.gather(approve(session_factory, approval_id, one), reject(session_factory, approval_id, two),
                                   return_exceptions=True)
    assert sum(isinstance(r, Exception) for r in results) == 1
    executions = db("SELECT count(*) AS n FROM executions")[0]["n"]
    assert (status_of(db, approval_id), executions, len(tools["payment_processor_sim"].calls)) in (
        ("APPROVED", 1, 1), ("REJECTED", 0, 0))


# ------------------------------------------------------------------------------------------ TOCTOU (spec 13.6)

async def test_a_payload_changed_after_the_request_is_blocked_and_never_runs(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    tampered = {"payee_id": "payee-0001", "amount": 999999, "currency": "USD", "reference": "inv-1"}
    db("ALTER TABLE actions DISABLE TRIGGER trg_actions_append_only")  # a tamperer who got past the append-only rule
    try:
        db("UPDATE actions SET action_payload = CAST(:p AS jsonb)", p=json.dumps(tampered))
    finally:
        db("ALTER TABLE actions ENABLE TRIGGER trg_actions_append_only")

    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))

    assert result.execution.execution_status.value == "BLOCKED"
    assert result.execution.error_code.value == "POLICY_REVALIDATION_FAILED"
    assert tools["payment_processor_sim"].calls == []
    assert "EXECUTION_REVALIDATION_FAILED" in events(db)


async def test_an_agent_disabled_after_the_request_is_blocked(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    db("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a", a=finance_id)
    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    assert (result.execution.execution_status.value, result.execution.error_code.value) == ("BLOCKED", "POLICY_REVALIDATION_FAILED")
    assert tools["payment_processor_sim"].calls == []


async def test_a_tool_that_is_missing_after_approval_leaves_the_approval_usable(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    del tools["payment_processor_sim"]
    result = await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    assert (result.execution.execution_status.value, result.execution.error_code.value) == ("FAILED", "TOOL_NOT_AVAILABLE")
    assert result.approval.consumed_at is None  # nothing ran, so nothing was consumed


# ------------------------------------------------------------------------------------------ cancel (APR-05)

async def test_cancelling_a_pending_approval(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    result = await cancel(session_factory, approval_id, actor_of(make_user, "boss", UserRole.ADMIN))
    assert result.execution is None and result.approval.approval_status.value == "CANCELLED"
    assert result.approval.reviewed_by_user_id is None and "APPROVAL_CANCELLED" in events(db)
    await raises(cancel(session_factory, approval_id, actor_of(make_user, "boss2", UserRole.ADMIN)), ErrorCode.APPROVAL_NOT_PENDING)
    await raises(approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER)), ErrorCode.APPROVAL_NOT_PENDING)
    assert tools["payment_processor_sim"].calls == [] and db("SELECT count(*) AS n FROM executions")[0]["n"] == 0


async def test_an_operator_may_cancel_but_a_reviewer_may_not(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    await raises(cancel(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER)), ErrorCode.AUTH_INSUFFICIENT_ROLE)
    assert status_of(db, approval_id) == "PENDING"
    result = await cancel(session_factory, approval_id, actor_of(make_user, "op2", UserRole.OPERATOR))
    assert result.approval.approval_status.value == "CANCELLED"


async def test_an_approved_approval_cannot_be_cancelled(client, make_user, finance_id, tools, risk, db, session_factory):
    approval_id = await held(client, make_user, finance_id, risk)
    await approve(session_factory, approval_id, actor_of(make_user, "rev1", UserRole.REVIEWER))
    await raises(cancel(session_factory, approval_id, actor_of(make_user, "boss", UserRole.ADMIN)), ErrorCode.APPROVAL_NOT_PENDING)
    assert status_of(db, approval_id) == "APPROVED"
