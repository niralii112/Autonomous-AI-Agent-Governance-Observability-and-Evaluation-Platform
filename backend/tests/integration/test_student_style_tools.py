"""The full flow with tools built the way Student 2 builds them (sync invoke, injected verifier, dict results)."""

import time

import pytest

from app.core.config import get_settings
from app.core.execution_grant import reset_nonce_store
from app.schemas import ActionSubmissionResponse
from app.services import execution_service
from tests.integration.api_support import audit_rows, client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import pay_body, risk, session_factory, world  # noqa: F401
from tests.tool_doubles import StudentStyleTool

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]


@pytest.fixture
def student_tool(monkeypatch):
    """Registers a payment tool built like Student 2's: it only runs with the verifier execution_service passes in."""
    reset_nonce_store()
    holder = {}

    def install(behaviour="ok", delay=0.0, verifier=execution_service._grant_verifier):
        holder["tool"] = StudentStyleTool("payment_processor_sim", verifier, behaviour, delay)
        monkeypatch.setattr(execution_service, "get_tool_implementation",
                            lambda name: holder["tool"] if name == "payment_processor_sim" else None)
        return holder["tool"]

    yield install
    reset_nonce_store()


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


async def submit(client, make_user, finance_id, amount=450):
    h = await headers_for(client, make_user, "ops", "OPERATOR")
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, amount), headers=h)
    assert r.status_code == 200, r.text
    return ActionSubmissionResponse.model_validate(r.json())


async def test_a_tool_built_like_student_2s_runs_through_the_whole_flow(client, make_user, finance_id, risk, student_tool):
    tool = student_tool("ok")
    resp = await submit(client, make_user, finance_id)
    assert resp.governance_decision.decision_rule_id == "D-13"
    assert resp.execution.execution_status.value == "SUCCEEDED" and resp.execution.result_summary == {"simulated": True}
    assert len(tool.calls) == 1  # her tool called our verifier, and the real grant passed


async def test_her_tool_refuses_to_run_when_it_has_no_verifier(client, make_user, finance_id, risk, student_tool):
    tool = student_tool("ok", verifier=None)  # her fail-closed default
    resp = await submit(client, make_user, finance_id)
    assert resp.execution.execution_status.value == "FAILED" and resp.execution.error_code.value == "EXECUTION_GRANT_INVALID"
    assert tool.calls == [] and resp.execution.error_message == "No execution-grant verifier is configured."


async def test_a_tool_that_rejects_the_payload_gives_a_failed_execution_with_her_message(client, make_user, finance_id, risk, student_tool):
    student_tool("invalid_payload")
    resp = await submit(client, make_user, finance_id)
    assert (resp.execution.execution_status.value, resp.execution.error_code.value) == ("FAILED", "TOOL_EXECUTION_FAILED")
    assert resp.execution.error_message == "The tool payload is invalid."


async def test_a_crashing_tool_is_failed_without_leaking_details(client, make_user, finance_id, risk, student_tool, db):
    student_tool("crash")
    resp = await submit(client, make_user, finance_id)
    assert resp.execution.error_code.value == "TOOL_EXECUTION_FAILED" and "secret" not in (resp.execution.error_message or "")
    assert "secret internal detail" not in str(db("SELECT * FROM executions")) + str(db("SELECT event_data FROM audit_events"))


async def test_a_slow_tool_times_out_and_the_request_returns_promptly(client, make_user, finance_id, risk, student_tool, monkeypatch):
    monkeypatch.setenv("EXECUTION_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    student_tool("slow", delay=3.0)
    started = time.perf_counter()
    resp = await submit(client, make_user, finance_id)
    assert resp.execution.error_code.value == "TOOL_EXECUTION_TIMEOUT" and time.perf_counter() - started < 2.8


@pytest.mark.parametrize("behaviour,message", [("bad_result", None), ("dict_failure", "declined")])
async def test_unusual_tool_answers_become_failed_executions(client, make_user, finance_id, risk, student_tool, behaviour, message):
    student_tool(behaviour)
    resp = await submit(client, make_user, finance_id)
    assert resp.execution.execution_status.value == "FAILED" and resp.execution.error_code.value == "TOOL_EXECUTION_FAILED"
    if message:
        assert resp.execution.error_message == message


async def test_the_audit_trail_shows_the_run_and_the_failure(client, make_user, finance_id, risk, student_tool, db):
    student_tool("invalid_payload")
    await submit(client, make_user, finance_id)
    assert audit_rows(db, "EXECUTION_STARTED") and audit_rows(db, "EXECUTION_FAILED")[0]["event_data"]["error_code"] == "TOOL_EXECUTION_FAILED"
