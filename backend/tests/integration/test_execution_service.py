"""execute_controlled_action and record_execution_result, driven directly (spec 12.7 and 13.6)."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.enums import ErrorCode, ExecutionStatus
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas import ExecutionOutcome
from app.services import execution_service
from tests.integration.api_support import audit_rows, client, db, env, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import FakeTool, session_factory, tools, world  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

PAYLOAD = {"payee_id": "payee-0001", "amount": 450, "currency": "USD", "reference": "inv-1"}


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


def make_pending(db, finance_id, *, payload=None, attempt=1, action_id=None, decision_id=None, approval=None, final="ALLOW"):
    """A PENDING execution built directly in the database, so tests can change the world before it runs."""
    payload = payload or PAYLOAD
    h = compute_payload_hash(payload)
    if action_id is None:
        action_id = db("INSERT INTO actions (agent_id,tool_id,requested_tool_name,action_type,action_payload,payload_hash,idempotency_key) "
                       "SELECT :a, tool_id, 'payment_processor_sim','FINANCE_PROPOSE_PAYMENT',CAST(:p AS jsonb),:h,:k "
                       "FROM tools WHERE tool_name='payment_processor_sim' RETURNING action_id",
                       a=finance_id, p=json.dumps(payload), h=h, k=uuid.uuid4().hex)[0]["action_id"]
    if decision_id is None:
        decision_id = db("INSERT INTO governance_decisions (action_id,decision_sequence,policy_result,final_decision,decision_reason_code,"
                         "decision_rule_id,matched_policy_ids,policy_snapshot_hash,payload_hash) VALUES (:a,1,'ALLOW',:f,'POLICY_ALLOW_LOW_RISK',"
                         "'D-13','[]'::jsonb,:s,:h) RETURNING governance_decision_id", a=action_id, f=final, s="b" * 64, h=h)[0]["governance_decision_id"]
    approval_id = None
    if approval is not None:
        approval_id = approval(action_id, decision_id, h)
    execution_id = db("INSERT INTO executions (action_id,governance_decision_id,approval_id,attempt_number,execution_status) "
                      "VALUES (:a,:d,:p,:n,'PENDING') RETURNING execution_id", a=action_id, d=decision_id, p=approval_id, n=attempt)[0]["execution_id"]
    return {"action": action_id, "decision": decision_id, "execution": execution_id, "approval": approval_id}


def approval_factory(db, make_user, status="APPROVED", consumed=False, expires_in=3600):
    reviewer = make_user("rev1", "REVIEWER")

    def make(action_id, decision_id, payload_hash):
        reviewed = status in ("APPROVED", "REJECTED")
        return db("INSERT INTO approval_requests (action_id,governance_decision_id,approval_status,payload_hash,expires_at,"
                  "reviewed_by_user_id,reviewed_at,consumed_at) VALUES (:a,:d,:s,:h, now() + make_interval(secs => :e),:r,"
                  "CASE WHEN :rev THEN now() END, CASE WHEN :c THEN now() END) RETURNING approval_id",
                  a=action_id, d=decision_id, s=status, h=payload_hash, e=expires_in, r=reviewer if reviewed else None,
                  rev=reviewed, c=consumed)[0]["approval_id"]

    return make


def force_status(db, execution_id, status):
    """Put an execution into any status, with the other columns the database requires for that status."""
    assert status in ("RUNNING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "PENDING")
    started = "now()" if status in ("RUNNING", "SUCCEEDED") else "NULL"
    completed = "now()" if status in ("SUCCEEDED", "FAILED", "BLOCKED") else "NULL"
    code = "'TOOL_EXECUTION_FAILED'" if status == "FAILED" else "NULL"
    db(f"UPDATE executions SET execution_status='{status}', started_at={started}, completed_at={completed}, "
       f"error_code={code} WHERE execution_id=:e", e=execution_id)


async def run(factory, execution_id):
    return await execution_service.execute_controlled_action(factory, execution_id)


def state(db, execution_id):
    return db("SELECT * FROM executions WHERE execution_id=:e", e=execution_id)[0]


# ================================ the happy path ==================================================

async def test_a_pending_execution_runs_the_tool_and_succeeds(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    result = await run(session_factory, ids["execution"])
    assert result.execution_status == ExecutionStatus.SUCCEEDED and result.result_summary == {"status": "done", "tool": "payment_processor_sim"}
    row = state(db, ids["execution"])
    assert (row["started_at"] is not None, row["completed_at"] is not None, row["error_code"], float(row["latency_ms"]) >= 0) == (True, True, None, True)
    assert [e["event_name"] for e in db("SELECT event_name FROM audit_events ORDER BY created_at")][-2:] == ["EXECUTION_STARTED", "EXECUTION_SUCCEEDED"]


async def test_the_tool_gets_a_grant_for_exactly_this_call(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    await run(session_factory, ids["execution"])
    [call] = tools["payment_processor_sim"].calls  # FakeTool verified the grant before recording the call
    assert (call.execution_id, call.action_id, call.tool_name) == (ids["execution"], ids["action"], "payment_processor_sim")
    assert call.action_payload == PAYLOAD and call.action_type.value == "FINANCE_PROPOSE_PAYMENT"


async def test_no_database_connection_is_held_while_the_tool_runs(session_factory, finance_id, tools, db):
    seen = {}

    class Probe(FakeTool):
        async def invoke(self, invocation, grant):
            seen["idle_in_transaction"] = db("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() "
                                            "AND state IN ('idle in transaction','idle in transaction (aborted)')")[0]["n"]
            return await super().invoke(invocation, grant)

    tools["payment_processor_sim"] = Probe()
    ids = make_pending(db, finance_id)
    await run(session_factory, ids["execution"])
    assert seen["idle_in_transaction"] == 0


async def test_a_span_named_execution_run_is_emitted(session_factory, finance_id, tools, db, monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(execution_service, "_tracer", provider.get_tracer("t"))
    await run(session_factory, make_pending(db, finance_id)["execution"])
    [span] = [s for s in exporter.get_finished_spans() if s.name == "execution.run"]
    assert span.attributes["execution.status"] == "SUCCEEDED"


# ================================ revalidation blocks the run ======================================

def assert_blocked(result, db, ids, tools, reason, code=ErrorCode.POLICY_REVALIDATION_FAILED):
    assert result.execution_status == ExecutionStatus.BLOCKED and result.error_code == code and result.started_at is None
    assert tools["payment_processor_sim"].calls == []
    event = [e for e in audit_rows(db, "EXECUTION_REVALIDATION_FAILED")][-1]
    assert event["event_data"]["reason"] == reason and event["outcome"] == "DENIED"
    assert state(db, ids["execution"])["execution_status"] == "BLOCKED"


async def test_a_disabled_agent_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a", a=finance_id)
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "agent_not_active")


async def test_a_disabled_tool_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("UPDATE tools SET tool_status='DISABLED' WHERE tool_name='payment_processor_sim'")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "tool_not_active")


@pytest.mark.parametrize("how", ["delete", "deny"])
async def test_a_revoked_permission_blocks_the_execution(session_factory, finance_id, tools, db, how):
    ids = make_pending(db, finance_id)
    if how == "delete":
        db("DELETE FROM agent_tool_permissions WHERE agent_id=:a", a=finance_id)
    else:
        db("UPDATE agent_tool_permissions SET is_allowed=false WHERE agent_id=:a", a=finance_id)
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "permission_revoked")


async def test_a_new_blocking_policy_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("INSERT INTO policies (policy_key,version,name,effect,priority,is_mandatory,conditions) VALUES ('freeze-payments',1,'f','BLOCK',1,true,"
       "CAST(:c AS jsonb))", c=json.dumps({"all": [{"field": "action_type", "operator": "EQ", "value": "FINANCE_PROPOSE_PAYMENT"}], "any": []}))
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "fresh_policy_block")


async def test_a_broken_policy_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("INSERT INTO policies (policy_key,version,name,effect,priority,conditions) VALUES ('broken',1,'b','ALLOW',500,CAST(:c AS jsonb))",
       c=json.dumps({"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []}))
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "fresh_policy_error")


async def test_a_changed_payload_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("ALTER TABLE actions DISABLE TRIGGER trg_actions_append_only")  # a tamperer who got past the append-only rule
    db("UPDATE actions SET action_payload = jsonb_set(action_payload, '{amount}', '49999') WHERE action_id=:a", a=ids["action"])
    db("ALTER TABLE actions ENABLE TRIGGER trg_actions_append_only")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "payload_changed")


async def test_a_decision_hash_that_does_not_match_blocks_the_execution(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    db("ALTER TABLE governance_decisions DISABLE TRIGGER trg_governance_decisions_append_only")
    db("UPDATE governance_decisions SET payload_hash=:h WHERE governance_decision_id=:d", h="c" * 64, d=ids["decision"])
    db("ALTER TABLE governance_decisions ENABLE TRIGGER trg_governance_decisions_append_only")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "payload_changed")


async def test_policy_drift_that_is_not_blocking_only_logs_and_still_runs(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)  # the stored snapshot hash is not what a fresh evaluation gives
    result = await run(session_factory, ids["execution"])
    assert result.execution_status == ExecutionStatus.SUCCEEDED and len(tools["payment_processor_sim"].calls) == 1


# ================================ approvals ========================================================

async def test_an_approved_unused_approval_is_consumed_when_the_execution_starts(session_factory, finance_id, tools, db, make_user):
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user), final="HUMAN_REVIEW")
    result = await run(session_factory, ids["execution"])
    assert result.execution_status == ExecutionStatus.SUCCEEDED and result.approval_id == ids["approval"]
    assert db("SELECT consumed_at FROM approval_requests WHERE approval_id=:a", a=ids["approval"])[0]["consumed_at"] is not None


async def test_an_already_used_approval_cannot_authorise_another_run(session_factory, finance_id, tools, db, make_user):
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user, consumed=True), final="HUMAN_REVIEW")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "approval_already_consumed", ErrorCode.APPROVAL_ALREADY_CONSUMED)


@pytest.mark.parametrize("status", ["PENDING", "REJECTED", "EXPIRED", "CANCELLED"])
async def test_an_approval_that_is_not_approved_blocks_the_execution(session_factory, finance_id, tools, db, make_user, status):
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user, status=status), final="HUMAN_REVIEW")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "approval_not_approved")
    assert db("SELECT consumed_at FROM approval_requests")[0]["consumed_at"] is None


async def test_an_expired_approval_blocks_the_execution_and_is_not_consumed(session_factory, finance_id, tools, db, make_user):
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user, expires_in=-60), final="HUMAN_REVIEW")
    assert_blocked(await run(session_factory, ids["execution"]), db, ids, tools, "approval_expired")
    assert db("SELECT consumed_at FROM approval_requests")[0]["consumed_at"] is None


async def test_a_blocked_run_does_not_use_up_the_approval(session_factory, finance_id, tools, db, make_user):
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user), final="HUMAN_REVIEW")
    db("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a", a=finance_id)
    await run(session_factory, ids["execution"])
    assert db("SELECT consumed_at FROM approval_requests")[0]["consumed_at"] is None


async def test_a_missing_tool_implementation_does_not_use_up_the_approval(session_factory, finance_id, tools, db, make_user):
    del tools["payment_processor_sim"]
    ids = make_pending(db, finance_id, approval=approval_factory(db, make_user), final="HUMAN_REVIEW")
    result = await run(session_factory, ids["execution"])
    assert result.error_code == ErrorCode.TOOL_NOT_AVAILABLE
    assert db("SELECT consumed_at FROM approval_requests")[0]["consumed_at"] is None


async def test_one_approval_can_start_only_one_execution_even_at_the_same_moment(session_factory, finance_id, tools, db, make_user):
    first = make_pending(db, finance_id, approval=approval_factory(db, make_user), final="HUMAN_REVIEW")
    second = make_pending(db, finance_id, action_id=first["action"], decision_id=first["decision"], attempt=2)
    db("UPDATE executions SET approval_id=:p WHERE execution_id=:e", p=first["approval"], e=second["execution"])
    results = await asyncio.gather(run(session_factory, first["execution"]), run(session_factory, second["execution"]))
    assert sorted(r.execution_status.value for r in results) == ["BLOCKED", "SUCCEEDED"]
    assert len(tools["payment_processor_sim"].calls) == 1
    assert {r.error_code for r in results} == {None, ErrorCode.APPROVAL_ALREADY_CONSUMED}


# ================================ state rules and concurrency ======================================

async def test_the_same_execution_started_twice_at_once_runs_the_tool_once(session_factory, finance_id, tools, db):
    ids = make_pending(db, finance_id)
    results = await asyncio.gather(run(session_factory, ids["execution"]), run(session_factory, ids["execution"]), return_exceptions=True)
    assert len(tools["payment_processor_sim"].calls) == 1
    errors = [r for r in results if isinstance(r, AppError)]
    assert len(errors) == 1 and errors[0].error_code == ErrorCode.INVALID_STATE_TRANSITION


@pytest.mark.parametrize("status", ["RUNNING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"])
async def test_only_a_pending_execution_can_be_executed(session_factory, finance_id, tools, db, status):
    ids = make_pending(db, finance_id)
    force_status(db, ids["execution"], status)
    with pytest.raises(AppError) as e:
        await run(session_factory, ids["execution"])
    assert e.value.error_code == ErrorCode.INVALID_STATE_TRANSITION and e.value.http_status == 409
    assert tools["payment_processor_sim"].calls == [] and state(db, ids["execution"])["execution_status"] == status


async def test_an_unknown_execution_is_not_found(session_factory, tools):
    with pytest.raises(AppError) as e:
        await run(session_factory, uuid.uuid4())
    assert e.value.error_code == ErrorCode.RESOURCE_NOT_FOUND


# ================================ record_execution_result ==========================================

async def set_running(db, ids):
    force_status(db, ids["execution"], "RUNNING")


async def test_record_result_stores_a_success(session_factory, finance_id, db):
    ids = make_pending(db, finance_id)
    await set_running(db, ids)
    async with session_factory() as s:
        r = await execution_service.record_execution_result(s, ids["execution"], ExecutionOutcome(
            execution_status=ExecutionStatus.SUCCEEDED, result_summary={"ok": True}, error_code=None, error_message=None, latency_ms=12.5))
        await s.commit()
    row = state(db, ids["execution"])
    assert (r.execution_status, row["execution_status"], row["result_summary"], float(row["latency_ms"])) == (ExecutionStatus.SUCCEEDED, "SUCCEEDED", {"ok": True}, 12.5)
    assert row["completed_at"] is not None and audit_rows(db, "EXECUTION_SUCCEEDED")


async def test_record_result_stores_a_failure_with_its_error_code(session_factory, finance_id, db):
    ids = make_pending(db, finance_id)
    await set_running(db, ids)
    async with session_factory() as s:
        await execution_service.record_execution_result(s, ids["execution"], ExecutionOutcome(
            execution_status=ExecutionStatus.FAILED, result_summary=None, error_code=ErrorCode.TOOL_EXECUTION_TIMEOUT,
            error_message="too slow", latency_ms=30000))
        await s.commit()
    row = state(db, ids["execution"])
    assert (row["execution_status"], row["error_code"], row["error_message"]) == ("FAILED", "TOOL_EXECUTION_TIMEOUT", "too slow")
    assert audit_rows(db, "EXECUTION_FAILED")[0]["outcome"] == "FAILURE"


@pytest.mark.parametrize("status", ["PENDING", "SUCCEEDED", "FAILED", "BLOCKED"])
async def test_record_result_only_accepts_a_running_execution(session_factory, finance_id, db, status):
    ids = make_pending(db, finance_id)
    force_status(db, ids["execution"], status)
    async with session_factory() as s:
        with pytest.raises(AppError) as e:
            await execution_service.record_execution_result(s, ids["execution"], ExecutionOutcome(
                execution_status=ExecutionStatus.SUCCEEDED, result_summary={}, error_code=None, error_message=None, latency_ms=1))
    assert e.value.error_code == ErrorCode.INVALID_STATE_TRANSITION


@pytest.mark.parametrize("bad", [ExecutionStatus.PENDING, ExecutionStatus.RUNNING, ExecutionStatus.BLOCKED, ExecutionStatus.CANCELLED])
async def test_record_result_refuses_a_non_final_status(session_factory, finance_id, db, bad):
    ids = make_pending(db, finance_id)
    await set_running(db, ids)
    async with session_factory() as s:
        with pytest.raises(AppError) as e:
            await execution_service.record_execution_result(s, ids["execution"], ExecutionOutcome(
                execution_status=bad, result_summary=None, error_code=None, error_message=None, latency_ms=1))
    assert e.value.error_code == ErrorCode.INVALID_STATE_TRANSITION


async def test_record_result_for_an_unknown_execution(session_factory):
    async with session_factory() as s:
        with pytest.raises(AppError) as e:
            await execution_service.record_execution_result(s, uuid.uuid4(), ExecutionOutcome(
                execution_status=ExecutionStatus.SUCCEEDED, result_summary={}, error_code=None, error_message=None, latency_ms=1))
    assert e.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
