"""The approval sweeper and the execution reconciler (spec 12.17, section 9.4)."""

import asyncio
import uuid

import pytest

from app.schemas import ActionSubmissionResponse
from app.services import background
from tests.integration.api_support import audit_rows, client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import pay_body, risk, session_factory, tools, world  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


async def submit(client, make_user, finance_id, amount):
    h = await headers_for(client, make_user, f"ops-{uuid.uuid4().hex[:8]}", "OPERATOR")
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, amount), headers=h)
    assert r.status_code == 200, r.text
    return ActionSubmissionResponse.model_validate(r.json())


# ------------------------------------------------------------------------------------------------ sweeper

async def test_the_sweeper_expires_only_approvals_past_their_time(client, make_user, finance_id, tools, risk, db, session_factory):
    old = await submit(client, make_user, finance_id, 5000)
    fresh = await submit(client, make_user, finance_id, 5001)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=old.approval.approval_id)

    assert await background.expire_pending_approvals(session_factory) == 1

    states = {r["approval_id"]: r["approval_status"] for r in db("SELECT approval_id, approval_status FROM approval_requests")}
    assert states[old.approval.approval_id] == "EXPIRED" and states[fresh.approval.approval_id] == "PENDING"
    events = audit_rows(db, "APPROVAL_EXPIRED")
    assert len(events) == 1 and events[0]["event_data"]["found_by"] == "sweeper" and events[0]["actor_type"] == "SYSTEM"
    assert await background.expire_pending_approvals(session_factory) == 0  # nothing left to do


async def test_an_expired_approval_cannot_be_approved_after_the_sweeper(client, make_user, finance_id, tools, risk, db, session_factory):
    held = await submit(client, make_user, finance_id, 5000)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=held.approval.approval_id)
    await background.expire_pending_approvals(session_factory)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    r = await client.post(f"/api/v1/approvals/{held.approval.approval_id}/approve", json={}, headers=reviewer)
    assert r.status_code == 409 and r.json()["error_code"] == "APPROVAL_NOT_PENDING"
    assert tools["payment_processor_sim"].calls == []


# ------------------------------------------------------------------------------------------------ reconciler

def make_running(db, execution_id, minutes_ago):
    db("UPDATE executions SET execution_status='RUNNING', started_at = now() - make_interval(mins => :m), "
       "completed_at=NULL, error_code=NULL, error_message=NULL, result_summary=NULL, latency_ms=NULL WHERE execution_id=:e",
       m=minutes_ago, e=execution_id)


async def test_the_reconciler_fails_an_execution_that_has_been_running_too_long(client, make_user, finance_id, tools, risk, db, session_factory):
    done = await submit(client, make_user, finance_id, 450)
    make_running(db, done.execution.execution_id, 10)  # EXECUTION_TIMEOUT_SECONDS is 30, so the limit is 60 seconds

    assert await background.reconcile_stale_executions(session_factory) == 1

    row = db("SELECT * FROM executions WHERE execution_id=:e", e=done.execution.execution_id)[0]
    assert (row["execution_status"], row["error_code"]) == ("FAILED", "EXECUTION_RESULT_UNRECORDED")
    assert row["completed_at"] is not None
    events = audit_rows(db, "EXECUTION_RESULT_UNRECORDED")
    assert len(events) == 1 and events[0]["outcome"] == "FAILURE"
    assert await background.reconcile_stale_executions(session_factory) == 0


async def test_the_reconciler_leaves_a_recent_running_execution_alone(client, make_user, finance_id, tools, risk, db, session_factory):
    done = await submit(client, make_user, finance_id, 450)
    make_running(db, done.execution.execution_id, 0)  # started just now
    assert await background.reconcile_stale_executions(session_factory) == 0
    assert db("SELECT execution_status FROM executions")[0]["execution_status"] == "RUNNING"


async def test_a_reconciled_execution_can_then_be_retried(client, make_user, finance_id, tools, risk, db, session_factory):
    done = await submit(client, make_user, finance_id, 450)
    make_running(db, done.execution.execution_id, 10)
    await background.reconcile_stale_executions(session_factory)
    h = await headers_for(client, make_user, "ops2", "OPERATOR")
    r = await client.post(f"/api/v1/actions/{done.action.action_id}/retry", headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["execution"]["attempt_number"], r.json()["execution"]["execution_status"]) == (2, "SUCCEEDED")


# ------------------------------------------------------------------------------------------------ the loop

async def test_the_loop_runs_a_round_and_stops_cleanly(client, make_user, finance_id, tools, risk, db, session_factory):
    held = await submit(client, make_user, finance_id, 5000)
    db("UPDATE approval_requests SET expires_at = now() - interval '1 minute' WHERE approval_id=:a", a=held.approval.approval_id)
    handle = background.start_background_tasks(session_factory, interval_seconds=0.05)
    try:
        for _ in range(50):
            await asyncio.sleep(0.1)
            if db("SELECT approval_status FROM approval_requests")[0]["approval_status"] == "EXPIRED":
                break
        assert db("SELECT approval_status FROM approval_requests")[0]["approval_status"] == "EXPIRED"
    finally:
        await background.stop_background_tasks(handle)
    assert handle.task.done()


async def test_the_loop_survives_a_failing_round(monkeypatch, session_factory):
    calls = []

    async def broken(_):
        calls.append(1)
        raise RuntimeError("database went away")

    monkeypatch.setattr(background, "expire_pending_approvals", broken)
    handle = background.start_background_tasks(session_factory, interval_seconds=0.05)
    await asyncio.sleep(0.4)
    assert not handle.task.done() and len(calls) >= 2  # it kept trying
    await background.stop_background_tasks(handle)
    assert handle.task.done()
