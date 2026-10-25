"""evaluate_policy (the policy engine) and POL-06, against a real database with the 10 seed policies."""

import hashlib
import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.enums import ActionType, AgentCategory, ErrorCode, PolicyResult, ToolSensitivity
from app.schemas import PolicyEvaluationRequest, PolicyEvaluationResponse
from app.services import policy_service
from tests.integration.api_support import (  # noqa: F401  (fixtures are used by name)
    audit_rows, auth, client, db, env, headers_for, make_user, token_of,
)
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
_spec = importlib.util.spec_from_file_location("seed_script_engine", SEED_PATH)
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)

FINANCE_AGENT = uuid.UUID("3f2b8c1e-5a4d-4e6f-9b1a-0c7d2e8f4a11")


@pytest.fixture
async def factory():
    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


@pytest.fixture
async def seeded(factory):
    async with factory() as s:
        await seed.seed_policies(s)
        await s.commit()


async def evaluate(factory, **kw) -> PolicyEvaluationResponse:
    """Call the engine the way a real caller does: the caller owns the transaction and commits."""
    async with factory() as s:
        response = await policy_service.evaluate_policy(s, make_request(**kw))
        await s.commit()
        return response


def make_request(action_type="FINANCE_PROPOSE_PAYMENT", payload=None, sensitivity=None, category="FINANCE",
                 tool="payment_processor_sim", agent=FINANCE_AGENT, action_id=None):
    return PolicyEvaluationRequest(
        action_id=action_id, agent_id=agent, agent_category=AgentCategory(category), action_type=ActionType(action_type),
        tool_name=tool, tool_sensitivity=ToolSensitivity(sensitivity) if sensitivity else None, action_payload=payload or {})


def pay(amount, payee="payee-0001"):
    return dict(action_type="FINANCE_PROPOSE_PAYMENT", sensitivity="WRITE",
                payload={"payee_id": payee, "amount": amount, "currency": "USD", "reference": "inv-1"})


def keys(response):
    return sorted(m.policy_key for m in response.matched_policies)


def add_policy(db, key, effect, priority, conditions, mandatory=False, active=True, version=1, **scope):
    return db("INSERT INTO policies (policy_key,version,name,effect,priority,is_mandatory,is_active,conditions,"
              "scope_agent_id,scope_agent_category,scope_action_type) VALUES (:k,:v,:k,:e,:p,:m,:a,CAST(:c AS jsonb),:sa,:sc,:st) "
              "RETURNING policy_id", k=key, v=version, e=effect, p=priority, m=mandatory, a=active, c=json.dumps(conditions),
              sa=scope.get("agent_id"), sc=scope.get("category"), st=scope.get("action_type"))[0]["policy_id"]


ALL_PAYMENTS = {"all": [{"field": "action_type", "operator": "EQ", "value": "FINANCE_PROPOSE_PAYMENT"}], "any": []}


# ================================ the seed policies, decision by decision ==========================

@pytest.mark.parametrize("amount,result,matched", [
    (1, PolicyResult.ALLOW, ["allow-small-payment"]),
    (450, PolicyResult.ALLOW, ["allow-small-payment"]),
    (1000, PolicyResult.ALLOW, ["allow-small-payment"]),
    (1000.01, PolicyResult.HUMAN_REVIEW, ["review-large-payment"]),
    (50000, PolicyResult.HUMAN_REVIEW, ["review-large-payment"]),
    (50000.01, PolicyResult.BLOCK, ["block-large-payment", "review-large-payment"]),
    (60000, PolicyResult.BLOCK, ["block-large-payment", "review-large-payment"]),
])
async def test_payment_thresholds(factory, seeded, amount, result, matched):
    r = await evaluate(factory, **pay(amount))
    assert r.policy_result == result and keys(r) == matched and r.error_code is None


async def test_block_beats_review_and_the_response_says_so(factory, seeded):
    r = await evaluate(factory, **pay(60000))
    assert r.conflict_detected is True and r.evaluated_policy_count == 10
    winner = next(m for m in r.matched_policies if m.policy_id == r.winning_policy_id)
    assert (winner.policy_key, winner.is_mandatory, winner.effect.value) == ("block-large-payment", True, "BLOCK")


async def test_a_mandatory_block_beats_an_allow_even_for_a_tiny_amount(factory, seeded):
    r = await evaluate(factory, **pay(10, payee="payee-blocked-001"))
    assert r.policy_result == PolicyResult.BLOCK and keys(r) == ["allow-small-payment", "block-denylisted-payee"]
    assert r.conflict_detected is True


async def test_two_mandatory_blocks_tie_on_priority_and_the_key_decides(factory, seeded):
    r = await evaluate(factory, **pay(60000, payee="payee-blocked-001"))
    winner = next(m for m in r.matched_policies if m.policy_id == r.winning_policy_id)
    assert winner.policy_key == "block-denylisted-payee"  # "block-d..." comes before "block-l..."


@pytest.mark.parametrize("report,result", [("rpt-001", PolicyResult.ALLOW), ("rpt-restricted-001", PolicyResult.BLOCK)])
async def test_reports(factory, seeded, report, result):
    r = await evaluate(factory, action_type="FINANCE_GET_REPORT", sensitivity="READ_ONLY", payload={"report_id": report},
                       tool="finance_report_reader")
    assert r.policy_result == result


async def test_read_only_tools_are_allowed_by_sensitivity(factory, seeded):
    r = await evaluate(factory, action_type="SUPPORT_GET_TICKET", sensitivity="READ_ONLY", category="CUSTOMER_SUPPORT",
                       payload={"ticket_id": "T-1"}, tool="ticket_reader")
    assert r.policy_result == PolicyResult.ALLOW and keys(r) == ["allow-read-only-tools"]


@pytest.mark.parametrize("record_set,result", [("payroll", PolicyResult.HUMAN_REVIEW), ("bank_accounts", PolicyResult.HUMAN_REVIEW),
                                              ("marketing", PolicyResult.NO_MATCH)])
async def test_sensitive_records(factory, seeded, record_set, result):
    r = await evaluate(factory, action_type="FINANCE_ACCESS_SENSITIVE_RECORDS", sensitivity="SENSITIVE_READ",
                       payload={"record_set": record_set, "purpose": "audit"}, tool="finance_records_vault")
    assert r.policy_result == result


@pytest.mark.parametrize("amount,result", [(50, PolicyResult.ALLOW), (100, PolicyResult.ALLOW), (100.01, PolicyResult.HUMAN_REVIEW)])
async def test_refunds(factory, seeded, amount, result):
    r = await evaluate(factory, action_type="SUPPORT_PROPOSE_REFUND", sensitivity="WRITE", category="CUSTOMER_SUPPORT",
                       payload={"ticket_id": "T-1", "amount": amount, "currency": "USD", "reason": "late"}, tool="refund_processor_sim")
    assert r.policy_result == result


async def test_customer_info_always_needs_review(factory, seeded):
    r = await evaluate(factory, action_type="SUPPORT_ACCESS_CUSTOMER_INFO", sensitivity="SENSITIVE_READ", category="CUSTOMER_SUPPORT",
                       payload={"customer_id": "c-1", "fields": ["email"], "purpose": "help"}, tool="customer_info_accessor")
    assert r.policy_result == PolicyResult.HUMAN_REVIEW and keys(r) == ["review-customer-info"]


# ================================ no match, missing and odd values =================================

async def test_no_match_has_the_documented_shape(factory, seeded):
    r = await evaluate(factory, action_type="FINANCE_ACCESS_SENSITIVE_RECORDS", sensitivity="SENSITIVE_READ",
                       payload={"record_set": "marketing"}, tool="finance_records_vault")
    assert (r.policy_result, r.matched_policies, r.winning_policy_id, r.conflict_detected) == (PolicyResult.NO_MATCH, [], None, False)
    assert r.policy_snapshot_hash == hashlib.sha256(b"").hexdigest() and r.evaluated_policy_count == 10


@pytest.mark.parametrize("payload", [{}, {"payee_id": "p"}, {"amount": None}, {"amount": "1500"}, {"amount": True}])
async def test_a_payment_without_a_usable_amount_matches_nothing(factory, seeded, payload):
    r = await evaluate(factory, action_type="FINANCE_PROPOSE_PAYMENT", sensitivity="WRITE", payload=payload)
    assert r.policy_result == PolicyResult.NO_MATCH


async def test_no_policies_at_all_means_no_match(factory):
    r = await evaluate(factory, **pay(450))
    assert r.policy_result == PolicyResult.NO_MATCH and r.evaluated_policy_count == 0


# ================================ active versions, scope, precedence ===============================

async def test_an_inactive_policy_is_ignored(factory, seeded, db):
    db("UPDATE policies SET is_active=false WHERE policy_key='review-large-payment'")
    assert (await evaluate(factory, **pay(5000))).policy_result == PolicyResult.NO_MATCH
    assert (await evaluate(factory, **pay(5000))).evaluated_policy_count == 9


async def test_only_the_active_version_counts(factory, seeded, db):
    db("UPDATE policies SET is_active=false WHERE policy_key='review-large-payment'")
    add_policy(db, "review-large-payment", "HUMAN_REVIEW", 60, {"all": [
        {"field": "action_type", "operator": "EQ", "value": "FINANCE_PROPOSE_PAYMENT"},
        {"field": "payload.amount", "operator": "GT", "value": 2000}], "any": []}, version=2)
    assert (await evaluate(factory, **pay(1500))).policy_result == PolicyResult.NO_MATCH   # v1 would have said review
    r = await evaluate(factory, **pay(2500))
    assert r.policy_result == PolicyResult.HUMAN_REVIEW and r.matched_policies[0].version == 2


async def test_scope_by_category(factory, seeded, db):
    add_policy(db, "support-only-block", "BLOCK", 1, ALL_PAYMENTS, mandatory=True, category="CUSTOMER_SUPPORT")
    assert (await evaluate(factory, **pay(450))).policy_result == PolicyResult.ALLOW                 # finance agent: not considered
    assert (await evaluate(factory, **pay(450))).evaluated_policy_count == 10                         # ...so not even counted
    assert (await evaluate(factory, category="CUSTOMER_SUPPORT", **pay(450))).policy_result == PolicyResult.BLOCK


async def test_scope_by_agent_and_by_action_type(factory, seeded, db):
    other = db("INSERT INTO agents (agent_name,agent_category) VALUES ('other-agent','FINANCE') RETURNING agent_id")[0]["agent_id"]
    add_policy(db, "one-agent-block", "BLOCK", 1, ALL_PAYMENTS, mandatory=True, agent_id=other)
    add_policy(db, "refund-only-review", "HUMAN_REVIEW", 1, ALL_PAYMENTS, action_type="SUPPORT_PROPOSE_REFUND")
    assert (await evaluate(factory, **pay(450))).policy_result == PolicyResult.ALLOW
    assert (await evaluate(factory, agent=other, **pay(450))).policy_result == PolicyResult.BLOCK


async def test_a_non_mandatory_block_loses_to_a_higher_precedence_allow(factory, seeded, db):
    add_policy(db, "soft-block-payments", "BLOCK", 150, ALL_PAYMENTS)
    r = await evaluate(factory, **pay(450))
    assert r.policy_result == PolicyResult.ALLOW and r.conflict_detected is True


async def test_a_high_precedence_allow_cannot_override_a_mandatory_block(factory, seeded, db):
    add_policy(db, "allow-all-payments-first", "ALLOW", 1, ALL_PAYMENTS)
    r = await evaluate(factory, **pay(10, payee="payee-blocked-001"))
    assert r.policy_result == PolicyResult.BLOCK


async def test_the_answer_is_deterministic_and_the_snapshot_hash_is_checkable(factory, seeded):
    first, second = await evaluate(factory, **pay(60000)), await evaluate(factory, **pay(60000))
    assert first.model_dump(exclude={"latency_ms"}) == second.model_dump(exclude={"latency_ms"})
    ids = ",".join(sorted(str(m.policy_id) for m in first.matched_policies))
    assert first.policy_snapshot_hash == hashlib.sha256(ids.encode()).hexdigest()


async def test_latency_is_reported(factory, seeded):
    assert (await evaluate(factory, **pay(450))).latency_ms >= 0


# ================================ failures fail closed =============================================

async def test_a_malformed_policy_gives_error_not_a_crash(factory, seeded, db):
    add_policy(db, "broken-policy", "BLOCK", 1, {"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []}, mandatory=True)
    r = await evaluate(factory, **pay(450))
    assert r.policy_result == PolicyResult.ERROR and r.error_code == ErrorCode.POLICY_ENGINE_FAILURE
    assert (r.matched_policies, r.winning_policy_id, r.conflict_detected) == ([], None, False)


async def test_a_malformed_second_leaf_is_found_even_when_the_first_leaf_is_false(factory, seeded, db):
    add_policy(db, "hidden-breakage", "BLOCK", 1, {"all": [
        {"field": "payload.amount", "operator": "GT", "value": 10 ** 9},
        {"field": "password", "operator": "EQ", "value": "x"}], "any": []}, mandatory=True)
    assert (await evaluate(factory, **pay(450))).policy_result == PolicyResult.ERROR


@pytest.mark.parametrize("conditions", [{"all": [], "any": []}, {"nonsense": 1}, {"all": "text", "any": []},
                                        {"all": [{"field": "payload.x", "operator": "SOMETIMES", "value": 1}], "any": []}])
async def test_unreadable_conditions_give_error(factory, seeded, db, conditions):
    add_policy(db, "garbled-policy", "ALLOW", 500, conditions)
    assert (await evaluate(factory, **pay(450))).policy_result == PolicyResult.ERROR


async def test_a_broken_database_session_gives_error_not_an_exception():
    class BrokenSession:
        async def execute(self, *_, **__):
            raise RuntimeError("database exploded")

    r = await policy_service.evaluate_policy(BrokenSession(), make_request(**pay(450)))
    assert r.policy_result == PolicyResult.ERROR and r.error_code == ErrorCode.POLICY_ENGINE_FAILURE


# ================================ audit and tracing ================================================

def make_action(db):
    agent = db("INSERT INTO agents (agent_id,agent_name,agent_category) VALUES (:i,'engine-test-agent','FINANCE') RETURNING agent_id",
               i=FINANCE_AGENT)[0]["agent_id"]
    action = db("INSERT INTO actions (agent_id,requested_tool_name,action_type,action_payload,payload_hash,idempotency_key) "
                "VALUES (:a,'payment_processor_sim','FINANCE_PROPOSE_PAYMENT','{}',:h,'k1') RETURNING action_id",
                a=agent, h="a" * 64)[0]["action_id"]
    return action


async def test_a_real_action_gets_a_policy_evaluated_audit_event(factory, seeded, db):
    action = make_action(db)
    r = await evaluate(factory, action_id=action, **pay(60000))
    assert r.policy_result == PolicyResult.BLOCK
    [event] = audit_rows(db, "POLICY_EVALUATED")
    assert event["action_id"] == action and event["agent_id"] == FINANCE_AGENT and event["actor_type"] == "SYSTEM"
    assert event["outcome"] == "SUCCESS" and event["event_data"]["policy_result"] == "BLOCK"
    assert event["event_data"]["policy_snapshot_hash"] == r.policy_snapshot_hash


async def test_a_dry_run_writes_nothing(factory, seeded, db):
    await evaluate(factory, action_id=None, **pay(60000))
    assert db("SELECT count(*) AS n FROM audit_events WHERE event_name LIKE 'POLICY_EVAL%'")[0]["n"] == 0


async def test_an_engine_failure_on_a_real_action_is_audited_as_failed(factory, seeded, db):
    add_policy(db, "broken-policy", "BLOCK", 1, {"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []})
    action = make_action(db)
    r = await evaluate(factory, action_id=action, **pay(450))
    assert r.policy_result == PolicyResult.ERROR
    [event] = audit_rows(db, "POLICY_EVALUATION_FAILED")
    assert event["outcome"] == "FAILURE" and event["event_data"]["error_code"] == "POLICY_ENGINE_FAILURE"
    assert audit_rows(db, "POLICY_EVALUATED") == []


async def test_if_the_audit_cannot_be_written_the_result_is_error_and_the_session_stays_usable(factory, seeded):
    from sqlalchemy import text

    async with factory() as s:
        r = await policy_service.evaluate_policy(s, make_request(action_id=uuid.uuid4(), **pay(450)))  # no such action: FK fails
        assert r.policy_result == PolicyResult.ERROR
        assert (await s.execute(text("SELECT 1"))).scalar_one() == 1  # the failed audit did not poison the transaction


async def test_a_span_named_policy_evaluate_is_emitted(factory, seeded, monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(policy_service, "_tracer", provider.get_tracer("test"))
    await evaluate(factory, **pay(60000))
    [span] = exporter.get_finished_spans()
    assert span.name == "policy.evaluate"
    assert span.attributes["policy.result"] == "BLOCK" and span.attributes["policy.matched_count"] == 2


# ================================ POL-06 dry-run endpoint ===========================================

async def test_dry_run_matches_the_service_and_follows_the_contract(client, make_user, db, seeded):
    h = await headers_for(client, make_user, "ops", "OPERATOR")
    example = json.loads((EXAMPLES / "POL-06.request.json").read_text())   # carries a made-up action_id
    r = await client.post("/api/v1/policies/evaluate", json=example, headers=h)
    assert r.status_code == 200
    body = PolicyEvaluationResponse.model_validate(r.json())
    assert body.policy_result == PolicyResult.ALLOW and [m.policy_key for m in body.matched_policies] == ["allow-small-payment"]
    assert set(r.json()) == set(json.loads((EXAMPLES / "POL-06.response.json").read_text()))
    assert db("SELECT count(*) AS n FROM audit_events WHERE event_name LIKE 'POLICY_EVAL%'")[0]["n"] == 0   # no persistence


@pytest.mark.parametrize("role,status", [("ADMIN", 200), ("OPERATOR", 200), ("REVIEWER", 403), ("VIEWER", 403)])
async def test_dry_run_roles(client, make_user, seeded, role, status):
    h = await headers_for(client, make_user, "someone", role)
    body = json.loads((EXAMPLES / "POL-06.request.json").read_text())
    r = await client.post("/api/v1/policies/evaluate", json=body, headers=h)
    assert r.status_code == status


async def test_dry_run_needs_login(client):
    assert (await client.post("/api/v1/policies/evaluate", json={})).status_code == 401


@pytest.mark.parametrize("patch", [{"agent_id": "not-a-uuid"}, {"action_type": "MAKE_COFFEE"}, {"agent_category": "PIRATE"},
                                   {"action_payload": "text"}, {"surprise": 1}, {"tool_name": None}])
async def test_dry_run_validation(client, make_user, seeded, patch):
    h = await headers_for(client, make_user, "ops", "OPERATOR")
    body = {**json.loads((EXAMPLES / "POL-06.request.json").read_text()), **patch}
    r = await client.post("/api/v1/policies/evaluate", json=body, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_dry_run_reports_an_engine_failure_inside_a_200(client, make_user, db, seeded):
    add_policy(db, "broken-policy", "BLOCK", 1, {"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []})
    h = await headers_for(client, make_user, "ops", "OPERATOR")
    r = await client.post("/api/v1/policies/evaluate", json=json.loads((EXAMPLES / "POL-06.request.json").read_text()), headers=h)
    assert r.status_code == 200 and r.json()["policy_result"] == "ERROR" and r.json()["error_code"] == "POLICY_ENGINE_FAILURE"


async def test_dry_run_with_a_blocking_payment(client, make_user, seeded):
    h = await headers_for(client, make_user, "ops", "OPERATOR")
    body = json.loads((EXAMPLES / "POL-06.request.json").read_text())
    body["action_payload"]["amount"] = 75000.0
    r = (await client.post("/api/v1/policies/evaluate", json=body, headers=h)).json()
    assert r["policy_result"] == "BLOCK" and r["conflict_detected"] is True
