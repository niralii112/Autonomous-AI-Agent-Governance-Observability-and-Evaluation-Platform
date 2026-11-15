"""retry_action and ACT-04 (spec 9.4, 12.17; FR-13, T-14).

A failed ALLOW action gets a NEW execution (attempt_number + 1); an action whose approval expired gets a NEW decision
(decision_sequence + 1) and a new approval. Nothing else may be retried, and attempts are limited."""

import asyncio
import uuid

import pytest

from app.schemas import ActionSubmissionResponse
from tests.integration.api_support import audit_rows, client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import FakeTool, pay_body, risk, session_factory, tools, world  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


async def operator(client, make_user, name="ops"):
    return await headers_for(client, make_user, name, "OPERATOR")


async def submit(client, headers, finance_id, amount):
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, amount), headers=headers)
    assert r.status_code == 200, r.text
    return ActionSubmissionResponse.model_validate(r.json())


def retry_url(action_id):
    return f"/api/v1/actions/{action_id}/retry"


def count(db, table):
    return db(f"SELECT count(*) AS n FROM {table}")[0]["n"]


# ---------------------------------------------------------------------------------- failed execution -> new attempt

async def test_a_failed_execution_is_retried_as_a_new_attempt(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    tools["payment_processor_sim"].mode = "fail"
    first = await submit(client, h, finance_id, 450)
    assert first.execution.execution_status.value == "FAILED"

    tools["payment_processor_sim"].mode = "ok"
    r = await client.post(retry_url(first.action.action_id), headers=h)

    assert r.status_code == 200, r.text
    body = ActionSubmissionResponse.model_validate(r.json())
    assert (body.execution.execution_status.value, body.execution.attempt_number) == ("SUCCEEDED", 2)
    assert body.duplicate is False and body.action.action_id == first.action.action_id
    assert body.governance_decision.governance_decision_id == first.governance_decision.governance_decision_id
    assert count(db, "executions") == 2 and count(db, "governance_decisions") == 1  # the history is kept
    statuses = [x["execution_status"] for x in db("SELECT execution_status FROM executions ORDER BY attempt_number")]
    assert statuses == ["FAILED", "SUCCEEDED"]


async def test_attempts_are_limited(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    tools["payment_processor_sim"].mode = "fail"
    first = await submit(client, h, finance_id, 450)
    for attempt in (2, 3):  # EXECUTION_MAX_ATTEMPTS defaults to 3
        r = await client.post(retry_url(first.action.action_id), headers=h)
        assert r.status_code == 200 and r.json()["execution"]["attempt_number"] == attempt
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "EXECUTION_RETRY_NOT_ALLOWED"
    assert count(db, "executions") == 3


async def test_a_succeeded_action_cannot_be_retried(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 450)
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "EXECUTION_RETRY_NOT_ALLOWED"
    assert count(db, "executions") == 1 and len(tools["payment_processor_sim"].calls) == 1


async def test_a_blocked_action_cannot_be_retried(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 60000)
    assert first.execution.execution_status.value == "BLOCKED"
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "EXECUTION_RETRY_NOT_ALLOWED"
    assert tools["payment_processor_sim"].calls == []


async def test_a_retry_still_goes_through_revalidation(client, make_user, finance_id, tools, risk, db):
    """The agent is disabled after the first failure: the retry is BLOCKED and the tool is not called again."""
    h = await operator(client, make_user)
    tools["payment_processor_sim"].mode = "fail"
    first = await submit(client, h, finance_id, 450)
    db("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a", a=finance_id)
    tools["payment_processor_sim"].mode = "ok"
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["execution"]["execution_status"], r.json()["execution"]["error_code"]) == \
        ("BLOCKED", "POLICY_REVALIDATION_FAILED")
    assert len(tools["payment_processor_sim"].calls) == 1  # only the first (failed) attempt ever reached the tool


# ---------------------------------------------------------------------------------- expired approval -> new decision

async def test_an_expired_approval_is_retried_with_a_new_decision_and_approval(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 5000)
    assert first.governance_decision.final_decision.value == "HUMAN_REVIEW"
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a",
       a=first.approval.approval_id)

    r = await client.post(retry_url(first.action.action_id), headers=h)

    assert r.status_code == 200, r.text
    body = ActionSubmissionResponse.model_validate(r.json())
    assert body.governance_decision.governance_decision_id != first.governance_decision.governance_decision_id
    assert body.governance_decision.final_decision.value == "HUMAN_REVIEW"
    assert body.approval.approval_status.value == "PENDING" and body.approval.approval_id != first.approval.approval_id
    assert body.execution is None and tools["payment_processor_sim"].calls == []
    assert [x["decision_sequence"] for x in db("SELECT decision_sequence FROM governance_decisions ORDER BY 1")] == [1, 2]
    assert [x["approval_status"] for x in db("SELECT approval_status FROM approval_requests ORDER BY created_at")] == \
        ["EXPIRED", "PENDING"]
    assert audit_rows(db, "APPROVAL_EXPIRED")  # the lazy expiry was audited


async def test_a_pending_approval_that_is_still_valid_cannot_be_retried(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 5000)
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "EXECUTION_RETRY_NOT_ALLOWED"
    assert count(db, "approval_requests") == 1 and count(db, "governance_decisions") == 1


async def test_a_rejected_approval_cannot_be_retried(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 5000)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    r = await client.post(f"/api/v1/approvals/{first.approval.approval_id}/reject",
                          json={"review_comment": "No"}, headers=reviewer)
    assert r.status_code == 200, r.text
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "EXECUTION_RETRY_NOT_ALLOWED"


async def test_the_retry_decision_can_differ_from_the_first_one(client, make_user, finance_id, tools, risk, db):
    """Risk is evaluated again: a retry after expiry with a CRITICAL score is still held, never relaxed."""
    h = await operator(client, make_user)
    first = await submit(client, h, finance_id, 5000)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a",
       a=first.approval.approval_id)
    risk.level = "CRITICAL"
    r = await client.post(retry_url(first.action.action_id), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["governance_decision"]["final_decision"] in ("HUMAN_REVIEW", "BLOCK")
    assert len(risk.requests) == 2  # the model was asked again


# ---------------------------------------------------------------------------------- access and errors

@pytest.mark.parametrize("role", ["REVIEWER", "VIEWER"])
async def test_only_admin_and_operator_may_retry(client, make_user, finance_id, tools, risk, db, role):
    h = await operator(client, make_user)
    tools["payment_processor_sim"].mode = "fail"
    first = await submit(client, h, finance_id, 450)
    other = await headers_for(client, make_user, "someone", role)
    r = await client.post(retry_url(first.action.action_id), headers=other)
    assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"
    assert count(db, "executions") == 1


async def test_retry_needs_login_and_a_known_action(client, make_user, finance_id, tools, risk):
    assert (await client.post(retry_url(uuid.uuid4()))).status_code == 401
    h = await operator(client, make_user)
    r = await client.post(retry_url(uuid.uuid4()), headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"


async def test_two_retries_at_once_run_the_tool_once(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    tools["payment_processor_sim"].mode = "fail"
    first = await submit(client, h, finance_id, 450)
    tools["payment_processor_sim"].mode = "ok"
    results = await asyncio.gather(*[client.post(retry_url(first.action.action_id), headers=h) for _ in range(2)])
    assert sorted(r.status_code for r in results) == [200, 409]
    assert count(db, "executions") == 2
    assert len(tools["payment_processor_sim"].calls) == 2  # the failed first attempt plus exactly one retry
