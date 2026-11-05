"""The whole submit_action flow through the real API and a real database (spec scenarios T-01 to T-19)."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.enums import ErrorCode
from app.schemas import ActionSubmissionResponse
from app.services import action_service, execution_service
from tests.integration.api_support import (  # noqa: F401  (fixtures are used by name)
    audit_rows, auth, client, db, env, headers_for, make_user, token_of,
)
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import (  # noqa: F401
    EXAMPLES, FakeTool, pay_body, risk, session_factory, tools, world,
)

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


@pytest.fixture
def support_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='support-agent-01'")[0]["agent_id"]


async def operator(client, make_user):
    return await headers_for(client, make_user, "ops", "OPERATOR")


async def submit(client, h, body, expect=200):
    r = await client.post("/api/v1/actions", json=body, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def rows(db, sql, **p):
    return db(sql, **p)


def events(db):
    return [r["event_name"] for r in db("SELECT event_name FROM audit_events ORDER BY created_at, audit_event_id")]


# ======================================= the three main outcomes ====================================

async def test_t01_a_small_payment_is_allowed_and_executed(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    resp = ActionSubmissionResponse.model_validate(body)
    assert (resp.governance_decision.final_decision.value, resp.governance_decision.decision_rule_id) == ("ALLOW", "D-13")
    assert resp.policy_evaluation.policy_result.value == "ALLOW" and resp.risk_assessment.risk_level.value == "LOW"
    assert resp.execution.execution_status.value == "SUCCEEDED" and resp.execution.attempt_number == 1
    assert resp.execution.result_summary == {"status": "done", "tool": "payment_processor_sim"}
    assert resp.approval is None and resp.duplicate is False
    assert len(tools["payment_processor_sim"].calls) == 1


async def test_t01_the_audit_trail_tells_the_whole_story_in_order(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    await submit(client, h, pay_body(finance_id, 450))
    names = events(db)
    names = names[names.index("ACTION_SUBMITTED"):]  # everything the submission caused, in order
    assert names == ["ACTION_SUBMITTED", "POLICY_EVALUATED", "RISK_ASSESSED", "GOVERNANCE_DECISION_MADE",
                     "EXECUTION_STARTED", "EXECUTION_SUCCEEDED"]


async def test_t01_everything_is_stored_and_linked(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450, key="k-store"))
    aid = body["action"]["action_id"]
    [a] = db("SELECT * FROM actions WHERE action_id=:a", a=aid)
    assert (a["tool_id"] is not None, a["idempotency_key"], str(a["agent_id"])) == (True, "k-store", str(finance_id))
    [d] = db("SELECT * FROM governance_decisions WHERE action_id=:a", a=aid)
    [r] = db("SELECT * FROM risk_assessments WHERE action_id=:a", a=aid)
    [e] = db("SELECT * FROM executions WHERE action_id=:a", a=aid)
    assert d["risk_assessment_id"] == r["risk_assessment_id"] and e["governance_decision_id"] == d["governance_decision_id"]
    assert d["payload_hash"] == a["payload_hash"] and d["decision_sequence"] == 1
    assert (e["execution_status"], e["started_at"] is not None, e["completed_at"] is not None) == ("SUCCEEDED", True, True)


async def test_t02_a_large_payment_waits_for_a_human(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 5000)))
    assert (resp.governance_decision.final_decision.value, resp.governance_decision.decision_rule_id) == ("HUMAN_REVIEW", "D-08")
    assert resp.approval.approval_status.value == "PENDING" and resp.execution is None
    assert resp.approval.expires_at > datetime.now(timezone.utc) + timedelta(minutes=50)
    assert tools["payment_processor_sim"].calls == []
    assert "APPROVAL_REQUESTED" in events(db) and "EXECUTION_STARTED" not in events(db)
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 0


async def test_t03_a_huge_payment_is_blocked_and_never_runs(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 60000)))
    assert (resp.governance_decision.final_decision.value, resp.governance_decision.decision_rule_id) == ("BLOCK", "D-06")
    assert resp.execution.execution_status.value == "BLOCKED" and resp.execution.started_at is None
    assert resp.approval is None and tools["payment_processor_sim"].calls == []
    assert "EXECUTION_BLOCKED" in events(db)


async def test_t04_a_mandatory_policy_beats_a_low_risk_score(client, make_user, finance_id, tools, risk):
    risk.level = "LOW"
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 10, payee="payee-blocked-001")))
    assert resp.risk_assessment.risk_level.value == "LOW"
    assert resp.governance_decision.final_decision.value == "BLOCK" and tools["payment_processor_sim"].calls == []


async def test_the_response_has_the_shape_of_the_contract_example(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    expected = json.loads((EXAMPLES / "ACT-01.response.json").read_text())
    assert set(body) == set(expected) and set(body["action"]) == set(expected["action"])
    assert set(body["execution"]) == set(expected["execution"])


# ======================================= risk changes the outcome only by adding restriction ========

@pytest.mark.parametrize("level,decision,rule", [("MEDIUM", "ALLOW", "D-13"), ("HIGH", "HUMAN_REVIEW", "D-11"), ("CRITICAL", "BLOCK", "D-07")])
async def test_risk_level_effect_on_an_allowed_payment(client, make_user, finance_id, tools, risk, level, decision, rule):
    risk.level = level
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert (resp.governance_decision.final_decision.value, resp.governance_decision.decision_rule_id) == (decision, rule)


async def test_critical_risk_blocks_even_a_policy_that_asked_for_review(client, make_user, finance_id, tools, risk):
    risk.level = "CRITICAL"
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 5000)))
    assert resp.governance_decision.decision_rule_id == "D-07" and resp.approval is None


async def test_fallback_risk_on_a_write_tool_needs_review(client, make_user, finance_id, tools, risk, db):
    risk.source, risk.model_version = "HEURISTIC_FALLBACK", "heuristic-v1"
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.governance_decision.decision_rule_id == "D-12" and resp.approval.approval_status.value == "PENDING"
    assert "RISK_FALLBACK_USED" in events(db)


async def test_fallback_risk_is_fine_for_a_read_only_tool(client, make_user, finance_id, tools, risk):
    risk.source, risk.model_version = "HEURISTIC_FALLBACK", "heuristic-v1"
    h = await operator(client, make_user)
    body = {"agent_id": str(finance_id), "tool_name": "finance_report_reader", "action_type": "FINANCE_GET_REPORT",
            "action_payload": {"report_id": "rpt-001", "period": "2026-Q3"}, "idempotency_key": uuid.uuid4().hex}
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, body))
    assert resp.governance_decision.final_decision.value == "ALLOW" and tools["finance_report_reader"].calls


@pytest.mark.parametrize("mode", ["raise", "hang", "other_action"])
async def test_a_broken_risk_model_means_review_never_allow(client, make_user, finance_id, tools, risk, db, monkeypatch, mode):
    monkeypatch.setattr(action_service, "RISK_TIMEOUT_SECONDS", 0.1)
    risk.mode = mode
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.risk_assessment is None
    assert (resp.governance_decision.final_decision.value, resp.governance_decision.decision_rule_id) == ("HUMAN_REVIEW", "D-10")
    assert tools["payment_processor_sim"].calls == []
    failed = [r for r in db("SELECT outcome, event_data FROM audit_events WHERE event_name='RISK_ASSESSED'")]
    assert failed and failed[0]["outcome"] == "FAILURE"


async def test_a_risk_answer_given_as_a_valid_dict_is_accepted(client, make_user, finance_id, tools, risk, db):
    risk.mode = "as_dict"  # Student 2's assess_risk returns a dict today
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.risk_assessment.risk_level.value == "LOW" and resp.governance_decision.decision_rule_id == "D-13"
    assert db("SELECT count(*) AS n FROM risk_assessments")[0]["n"] == 1


@pytest.mark.parametrize("mode", ["invalid_dict", "not_an_assessment"])
async def test_a_risk_answer_that_is_not_a_valid_assessment_means_review(client, make_user, finance_id, tools, risk, db, mode):
    risk.mode = mode
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.risk_assessment is None and resp.governance_decision.decision_rule_id == "D-10"
    assert db("SELECT event_data FROM audit_events WHERE event_name='RISK_ASSESSED'")[0]["event_data"]["reason"] == "risk_response_invalid"
    assert tools["payment_processor_sim"].calls == []


async def test_a_broken_risk_model_cannot_unblock_a_policy_block(client, make_user, finance_id, tools, risk, monkeypatch):
    risk.mode = "raise"
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 60000)))
    assert resp.governance_decision.decision_rule_id == "D-06"


async def test_the_risk_model_receives_the_real_facts(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    await submit(client, h, pay_body(finance_id, 60000, key="blocked-1"))   # becomes a recent BLOCK
    await submit(client, h, pay_body(finance_id, 450, key="second"))
    request = risk.requests[-1]
    assert (request.agent_category.value, request.tool_name, request.tool_sensitivity.value) == ("FINANCE", "payment_processor_sim", "WRITE")
    assert request.context.agent_trust_tier == 2 and request.context.recent_blocked_count_24h == 1
    assert request.context.recent_failed_count_24h == 0 and request.action_payload["amount"] == 450


async def test_the_risk_assessment_is_stored_exactly_as_returned(client, make_user, finance_id, tools, risk, db):
    risk.level = "MEDIUM"
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    [r] = db("SELECT * FROM risk_assessments")
    sent = body["risk_assessment"]
    assert str(r["risk_assessment_id"]) == sent["risk_assessment_id"] and float(r["risk_score"]) == sent["risk_score"] == 0.4
    assert r["model_version"] == "risk-logreg-1.0.0" and r["risk_level"] == "MEDIUM"


async def test_an_unregistered_model_version_is_registered_inactive_and_noted(client, make_user, finance_id, tools, risk, db):
    risk.model_version = "risk-experimental-9"
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    assert body["risk_assessment"]["model_version"] == "risk-experimental-9"
    [m] = db("SELECT is_active, algorithm FROM model_versions WHERE model_version='risk-experimental-9'")
    assert m["is_active"] is False
    assert db("SELECT event_data FROM audit_events WHERE event_name='RISK_ASSESSED'")[0]["event_data"]["model_auto_registered"] is True


# ======================================= other reasons to block ========================================

async def test_t09_an_unknown_tool_is_stored_and_blocked(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450, tool="no_such_tool")))
    assert (resp.governance_decision.decision_rule_id, resp.execution.execution_status.value) == ("D-02", "BLOCKED")
    assert resp.action.tool_id is None and resp.risk_assessment is None and risk.requests == []


async def test_a_tool_that_does_not_support_the_action_type_is_treated_as_unknown(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 450, tool="finance_report_reader")  # a report reader cannot propose payments
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, body))
    assert resp.governance_decision.decision_rule_id == "D-02" and tools["finance_report_reader"].calls == []


async def test_a_disabled_agent_is_blocked_d01(client, make_user, finance_id, tools, risk, db):
    db("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a", a=finance_id)
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.governance_decision.decision_rule_id == "D-01" and tools["payment_processor_sim"].calls == []


async def test_a_disabled_tool_is_blocked_d03(client, make_user, finance_id, tools, risk, db):
    db("UPDATE tools SET tool_status='DISABLED' WHERE tool_name='payment_processor_sim'")
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.governance_decision.decision_rule_id == "D-03"


async def test_an_agent_without_permission_is_blocked_d04(client, make_user, finance_id, tools, risk, db):
    db("DELETE FROM agent_tool_permissions WHERE agent_id=:a", a=finance_id)
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.governance_decision.decision_rule_id == "D-04" and tools["payment_processor_sim"].calls == []


async def test_an_agent_denied_a_tool_by_the_seed_matrix_is_blocked_d04(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = {"agent_id": str(finance_id), "tool_name": "refund_processor_sim", "action_type": "SUPPORT_PROPOSE_REFUND",
            "action_payload": {"ticket_id": "T-1", "customer_id": "c-1", "amount": 10, "currency": "USD", "reason": "late"}, "idempotency_key": "x1"}
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, body))
    assert resp.governance_decision.decision_rule_id == "D-04"


async def test_a_broken_policy_engine_blocks_d05(client, make_user, finance_id, tools, risk, db):
    db("INSERT INTO policies (policy_key,version,name,effect,priority,conditions,is_active) "
       "VALUES ('broken',1,'b','ALLOW',500,CAST(:c AS jsonb),true)",
       c=json.dumps({"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []}))
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert (resp.governance_decision.decision_rule_id, resp.policy_evaluation.policy_result.value) == ("D-05", "ERROR")
    assert "POLICY_EVALUATION_FAILED" in events(db) and tools["payment_processor_sim"].calls == []


async def test_no_matching_policy_goes_to_review_d09(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = {"agent_id": str(finance_id), "tool_name": "finance_records_vault", "action_type": "FINANCE_ACCESS_SENSITIVE_RECORDS",
            "action_payload": {"record_set": "marketing", "record_count": 10, "justification": "audit"}, "idempotency_key": "nm1"}
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, body))
    assert resp.governance_decision.decision_rule_id == "D-09" and resp.governance_decision.final_decision.value == "HUMAN_REVIEW"


# ======================================= rejected before anything is stored ============================

async def test_t10_an_unknown_agent_is_404_and_nothing_is_stored(client, make_user, world, tools, risk, db):
    h = await operator(client, make_user)
    r = await client.post("/api/v1/actions", json=pay_body(uuid.uuid4(), 450), headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "AGENT_NOT_REGISTERED"
    assert db("SELECT count(*) AS n FROM actions")[0]["n"] == 0
    event = db("SELECT outcome, agent_id FROM audit_events WHERE event_name='ACTION_REJECTED_PRE_VALIDATION'")[0]
    assert event["outcome"] == "DENIED" and event["agent_id"] is None


@pytest.mark.parametrize("payload", [{}, {"payee_id": "p", "amount": -5, "currency": "USD", "reference": "r"},
                                     {"payee_id": "p", "amount": 5, "currency": "US", "reference": "r"},
                                     {"payee_id": "p", "amount": 5, "currency": "USD", "reference": "r", "extra": 1}])
async def test_t17_an_invalid_payload_is_422_and_nothing_is_stored(client, make_user, finance_id, tools, risk, db, payload):
    h = await operator(client, make_user)
    body = {**pay_body(finance_id), "action_payload": payload}
    r = await client.post("/api/v1/actions", json=body, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "INVALID_ACTION_PAYLOAD"
    assert db("SELECT count(*) AS n FROM actions")[0]["n"] == 0 and risk.requests == []
    assert db("SELECT outcome FROM audit_events WHERE event_name='ACTION_REJECTED_PRE_VALIDATION'")[0]["outcome"] == "DENIED"


@pytest.mark.parametrize("patch", [{"agent_id": "nope"}, {"action_type": "MAKE_COFFEE"}, {"idempotency_key": ""}, {"surprise": 1}, {"tool_name": None}])
async def test_a_malformed_request_is_422(client, make_user, finance_id, tools, risk, patch):
    h = await operator(client, make_user)
    r = await client.post("/api/v1/actions", json={**pay_body(finance_id), **patch}, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("role,status", [("ADMIN", 200), ("OPERATOR", 200), ("REVIEWER", 403), ("VIEWER", 403)])
async def test_only_admin_and_operator_may_submit(client, make_user, finance_id, tools, risk, role, status):
    h = await headers_for(client, make_user, "someone", role)
    assert (await client.post("/api/v1/actions", json=pay_body(finance_id, 450), headers=h)).status_code == status


async def test_submitting_needs_login(client, finance_id):
    assert (await client.post("/api/v1/actions", json=pay_body(finance_id))).status_code == 401


# ======================================= idempotency ===================================================

async def test_t13_the_same_key_and_payload_returns_the_original(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 450, key="same-key")
    first, second = await submit(client, h, body), await submit(client, h, body)
    assert first["duplicate"] is False and second["duplicate"] is True
    assert second["action"]["action_id"] == first["action"]["action_id"]
    assert second["governance_decision"]["governance_decision_id"] == first["governance_decision"]["governance_decision_id"]
    assert second["execution"]["execution_id"] == first["execution"]["execution_id"]
    assert second["policy_evaluation"]["policy_result"] == "ALLOW" and second["risk_assessment"]["risk_level"] == "LOW"
    assert len(tools["payment_processor_sim"].calls) == 1 and len(risk.requests) == 1
    assert db("SELECT count(*) AS n FROM actions")[0]["n"] == 1
    assert "ACTION_DUPLICATE_DETECTED" in events(db)


async def test_a_duplicate_of_a_review_returns_the_same_pending_approval(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 5000, key="rev")
    first, second = await submit(client, h, body), await submit(client, h, body)
    assert second["duplicate"] is True and second["approval"]["approval_id"] == first["approval"]["approval_id"]
    assert db("SELECT count(*) AS n FROM approval_requests")[0]["n"] == 1


async def test_a_duplicate_of_a_block_is_still_blocked_and_unchanged(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 60000, key="blk")
    first, second = await submit(client, h, body), await submit(client, h, body)
    assert second["duplicate"] is True and second["governance_decision"]["final_decision"] == "BLOCK"
    assert second["policy_evaluation"]["winning_policy_id"] == first["policy_evaluation"]["winning_policy_id"]
    assert second["policy_evaluation"]["conflict_detected"] is True


async def test_t14_the_same_key_with_a_different_payload_is_409(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    await submit(client, h, pay_body(finance_id, 450, key="k"))
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, 451, key="k"), headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert db("SELECT count(*) AS n FROM actions")[0]["n"] == 1


async def test_the_same_key_for_another_agent_is_independent(client, make_user, finance_id, support_id, tools, risk):
    h = await operator(client, make_user)
    a = await submit(client, h, pay_body(finance_id, 450, key="shared"))
    b = await submit(client, h, pay_body(support_id, 450, key="shared"))
    assert a["action"]["action_id"] != b["action"]["action_id"] and b["duplicate"] is False


async def test_the_key_is_compared_to_the_payload_ignoring_key_order(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    first = pay_body(finance_id, 450, key="order")
    second = {**first, "action_payload": dict(reversed(list(first["action_payload"].items())))}
    await submit(client, h, first)
    assert (await submit(client, h, second))["duplicate"] is True


async def test_two_identical_requests_at_the_same_moment_run_the_tool_once(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 450, key="race")
    results = await asyncio.gather(*[client.post("/api/v1/actions", json=body, headers=h) for _ in range(3)])
    assert [r.status_code for r in results] == [200, 200, 200]
    assert sorted(r.json()["duplicate"] for r in results) == [False, True, True]
    assert len({r.json()["action"]["action_id"] for r in results}) == 1
    assert len(tools["payment_processor_sim"].calls) == 1
    assert db("SELECT count(*) AS n FROM executions")[0]["n"] == 1 and db("SELECT count(*) AS n FROM governance_decisions")[0]["n"] == 1


async def test_an_action_left_without_a_decision_is_resumed_when_it_is_old(client, make_user, finance_id, tools, risk, db):
    h = await operator(client, make_user)
    body = pay_body(finance_id, 450, key="crashed")
    from app.core.hashing import compute_payload_hash
    db("INSERT INTO actions (agent_id,tool_id,requested_tool_name,action_type,action_payload,payload_hash,idempotency_key,created_at) "
       "SELECT :a, tool_id, 'payment_processor_sim','FINANCE_PROPOSE_PAYMENT',CAST(:p AS jsonb),:h,'crashed', now() - interval '5 minutes' "
       "FROM tools WHERE tool_name='payment_processor_sim'", a=finance_id, p=json.dumps(body["action_payload"]), h=compute_payload_hash(body["action_payload"]))
    resp = await submit(client, h, body)
    assert resp["governance_decision"]["final_decision"] == "ALLOW" and resp["duplicate"] is False
    assert db("SELECT count(*) AS n FROM actions")[0]["n"] == 1


async def test_an_action_still_being_processed_gives_409_after_a_short_wait(client, make_user, finance_id, tools, risk, db, monkeypatch):
    monkeypatch.setattr(action_service, "IN_FLIGHT_WAIT_SECONDS", 0.3)
    h = await operator(client, make_user)
    body = pay_body(finance_id, 450, key="slow")
    from app.core.hashing import compute_payload_hash
    db("INSERT INTO actions (agent_id,requested_tool_name,action_type,action_payload,payload_hash,idempotency_key) "
       "VALUES (:a,'payment_processor_sim','FINANCE_PROPOSE_PAYMENT',CAST(:p AS jsonb),:h,'slow')",
       a=finance_id, p=json.dumps(body["action_payload"]), h=compute_payload_hash(body["action_payload"]))
    r = await client.post("/api/v1/actions", json=body, headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "INVALID_STATE_TRANSITION"


# ======================================= what happens when the tool misbehaves ==========================

async def test_a_tool_that_reports_failure_is_a_failed_execution(client, make_user, finance_id, tools, risk, db):
    tools["payment_processor_sim"].mode = "fail"
    h = await operator(client, make_user)
    resp = ActionSubmissionResponse.model_validate(await submit(client, h, pay_body(finance_id, 450)))
    assert resp.execution.execution_status.value == "FAILED" and resp.execution.error_code == ErrorCode.TOOL_EXECUTION_FAILED
    assert resp.execution.error_message == "The payment was declined." and "EXECUTION_FAILED" in events(db)


async def test_a_tool_that_crashes_is_a_failed_execution_without_leaking_details(client, make_user, finance_id, tools, risk):
    tools["payment_processor_sim"].mode = "raise"
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    assert body["execution"]["execution_status"] == "FAILED" and body["execution"]["error_code"] == "TOOL_EXECUTION_FAILED"
    assert "secret internal detail" not in json.dumps(body)


async def test_a_tool_that_hangs_times_out(client, make_user, finance_id, tools, risk, monkeypatch):
    monkeypatch.setenv("EXECUTION_TIMEOUT_SECONDS", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()
    tools["payment_processor_sim"].mode = "hang"
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    assert body["execution"]["execution_status"] == "FAILED" and body["execution"]["error_code"] == "TOOL_EXECUTION_TIMEOUT"


async def test_a_missing_tool_implementation_is_a_failed_execution(client, make_user, finance_id, tools, risk):
    del tools["payment_processor_sim"]
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    assert body["execution"]["execution_status"] == "FAILED" and body["execution"]["error_code"] == "TOOL_NOT_AVAILABLE"
    assert body["execution"]["started_at"] is None


async def test_failed_executions_feed_the_risk_context_next_time(client, make_user, finance_id, tools, risk):
    tools["payment_processor_sim"].mode = "fail"
    h = await operator(client, make_user)
    await submit(client, h, pay_body(finance_id, 450, key="f1"))
    await submit(client, h, pay_body(finance_id, 450, key="f2"))
    assert risk.requests[-1].context.recent_failed_count_24h == 1


# ======================================= ACT-02 / ACT-03 ================================================

async def test_act03_returns_the_full_story_of_an_action(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    r = await client.get(f"/api/v1/actions/{body['action']['action_id']}", headers=h)
    assert r.status_code == 200
    detail = r.json()
    assert (len(detail["governance_decisions"]), len(detail["risk_assessments"]), len(detail["approvals"]), len(detail["executions"])) == (1, 1, 0, 1)
    assert detail["action"]["action_payload"]["amount"] == 450 and detail["action"]["payload_redacted"] is False


async def test_act03_hides_the_payload_from_a_viewer(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    body = await submit(client, h, pay_body(finance_id, 450))
    v = await headers_for(client, make_user, "watcher", "VIEWER")
    detail = (await client.get(f"/api/v1/actions/{body['action']['action_id']}", headers=v)).json()
    assert detail["action"]["action_payload"] is None and detail["action"]["payload_redacted"] is True
    assert detail["action"]["payload_hash"] == body["action"]["payload_hash"]
    for role in ("REVIEWER", "OPERATOR", "ADMIN"):
        other = await headers_for(client, make_user, f"user-{role.lower()}", role)
        assert (await client.get(f"/api/v1/actions/{body['action']['action_id']}", headers=other)).json()["action"]["action_payload"] is not None


async def test_act03_unknown_or_malformed_id(client, make_user, world):
    h = await operator(client, make_user)
    assert (await client.get(f"/api/v1/actions/{uuid.uuid4()}", headers=h)).status_code == 404
    assert (await client.get("/api/v1/actions/not-a-uuid", headers=h)).status_code == 422


async def test_act02_lists_the_latest_state_of_every_action(client, make_user, finance_id, tools, risk):
    h = await operator(client, make_user)
    allowed = await submit(client, h, pay_body(finance_id, 450, key="a"))
    review = await submit(client, h, pay_body(finance_id, 5000, key="b"))
    blocked = await submit(client, h, pay_body(finance_id, 60000, key="c"))
    page = (await client.get("/api/v1/actions", params={"sort_by": "created_at", "sort_order": "asc"}, headers=h)).json()
    got = {i["action_id"]: i for i in page["items"]}
    assert page["total_items"] == 3 and page["total_pages"] == 1
    a, b, c = (got[x["action"]["action_id"]] for x in (allowed, review, blocked))
    assert (a["final_decision"], a["execution_status"], a["approval_status"], a["risk_level"]) == ("ALLOW", "SUCCEEDED", None, "LOW")
    assert (b["final_decision"], b["execution_status"], b["approval_status"]) == ("HUMAN_REVIEW", None, "PENDING")
    assert (c["final_decision"], c["execution_status"], c["policy_result"]) == ("BLOCK", "BLOCKED", "BLOCK")
    assert a["agent_name"] == "finance-agent-01" and a["requested_tool_name"] == "payment_processor_sim"


async def test_act02_filters_paging_and_sorting(client, make_user, finance_id, support_id, tools, risk):
    h = await operator(client, make_user)
    risk.level = "LOW"
    await submit(client, h, pay_body(finance_id, 450, key="a"))
    risk.level = "MEDIUM"
    await submit(client, h, pay_body(finance_id, 5000, key="b"))
    risk.level = "HIGH"
    await submit(client, h, pay_body(support_id, 60000, key="c", tool="payment_processor_sim"))  # D-04: support agent has no payment tool

    async def total(**p):
        return (await client.get("/api/v1/actions", params=p, headers=h)).json()["total_items"]

    assert await total() == 3
    assert await total(agent_id=str(finance_id)) == 2 and await total(agent_id=str(support_id)) == 1
    assert await total(final_decision="BLOCK") == 1 and await total(final_decision="HUMAN_REVIEW") == 1
    assert await total(approval_status="PENDING") == 1 and await total(execution_status="SUCCEEDED") == 1
    assert await total(risk_level="MEDIUM") == 1 and await total(action_type="FINANCE_PROPOSE_PAYMENT") == 3
    assert await total(created_from="2999-01-01T00:00:00Z") == 0
    by_risk = (await client.get("/api/v1/actions", params={"sort_by": "risk_score", "sort_order": "desc"}, headers=h)).json()["items"]
    assert [i["risk_level"] for i in by_risk] == ["HIGH", "MEDIUM", "LOW"]
    page2 = (await client.get("/api/v1/actions", params={"page": 2, "page_size": 2}, headers=h)).json()
    assert len(page2["items"]) == 1 and page2["total_pages"] == 2


@pytest.mark.parametrize("params", [{"sort_by": "agent_id"}, {"page_size": 101}, {"page": 0}, {"action_type": "X"}, {"risk_level": "X"}, {"created_from": "soon"}])
async def test_act02_rejects_bad_query(client, make_user, world, params):
    h = await operator(client, make_user)
    assert (await client.get("/api/v1/actions", params=params, headers=h)).status_code == 422


async def test_every_logged_in_role_can_list_actions(client, make_user, world):
    for role in ("ADMIN", "REVIEWER", "OPERATOR", "VIEWER"):
        h = await headers_for(client, make_user, f"u-{role.lower()}", role)
        assert (await client.get("/api/v1/actions", headers=h)).status_code == 200
    assert (await client.get("/api/v1/actions")).status_code == 401
