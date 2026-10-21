import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.conftest import TEST_URL, run_alembic

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]

HASH = "a" * 64
EXPECTED_TABLES = {
    "users", "agents", "tools", "agent_tool_permissions", "policies", "actions",
    "risk_assessments", "governance_decisions", "approval_requests", "executions",
    "audit_events", "model_versions", "evaluation_results",
}


def one(conn, sql, **params):
    return conn.execute(text(sql), params).scalar_one()


def make_user(conn, role="REVIEWER"):
    name = f"u{uuid.uuid4().hex[:8]}"
    return one(conn, "INSERT INTO users (username,email,password_hash,role) "
                     "VALUES (:n,:e,'h',:r) RETURNING user_id", n=name, e=f"{name}@x.test", r=role)


def make_agent(conn, name=None):
    name = name or f"a{uuid.uuid4().hex[:8]}"
    return one(conn, "INSERT INTO agents (agent_name,agent_category) VALUES (:n,'FINANCE') "
                     "RETURNING agent_id", n=name)


def make_action(conn, agent_id=None, key=None):
    agent_id = agent_id or make_agent(conn)
    return one(conn, "INSERT INTO actions (agent_id,requested_tool_name,action_type,action_payload,"
                     "payload_hash,idempotency_key) VALUES (:a,'t','FINANCE_PROPOSE_PAYMENT',"
                     "CAST(:p AS jsonb),:h,:k) RETURNING action_id",
               a=agent_id, p=json.dumps({"amount": 1}), h=HASH, k=key or uuid.uuid4().hex)


def make_decision(conn, action_id, seq=1):
    return one(conn, "INSERT INTO governance_decisions (action_id,decision_sequence,policy_result,"
                     "final_decision,decision_reason_code,decision_rule_id,policy_snapshot_hash,"
                     "payload_hash) VALUES (:a,:s,'ALLOW','ALLOW','R','D-13',:h,:h) "
                     "RETURNING governance_decision_id", a=action_id, s=seq, h=HASH)


def test_all_13_tables_exist(conn):
    names = {r[0] for r in conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    assert EXPECTED_TABLES <= names


def test_bad_user_role_rejected(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO users (username,email,password_hash,role) "
                          "VALUES ('x','x@x.test','h','BOSS')"))


def test_user_defaults(conn):
    uid = make_user(conn, "VIEWER")
    row = conn.execute(text("SELECT is_active, created_at FROM users WHERE user_id=:u"), {"u": uid}).one()
    assert row.is_active is True and row.created_at is not None


def test_trust_tier_range(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO agents (agent_name,agent_category,trust_tier) "
                          "VALUES ('bad','FINANCE',4)"))


def test_agent_name_unique(conn):
    make_agent(conn, "dup-agent")
    with pytest.raises(IntegrityError):
        make_agent(conn, "dup-agent")


def test_policy_mandatory_must_block(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO policies (policy_key,name,effect,priority,is_mandatory,conditions)"
                          " VALUES ('k','n','ALLOW',5,true,'{}')"))


def test_policy_priority_range(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO policies (policy_key,name,effect,priority,conditions)"
                          " VALUES ('k','n','BLOCK',0,'{}')"))


def test_only_one_active_version_per_policy_key(conn):
    conn.execute(text("INSERT INTO policies (policy_key,version,name,effect,priority,conditions)"
                      " VALUES ('same',1,'n','BLOCK',5,'{}')"))
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO policies (policy_key,version,name,effect,priority,conditions)"
                          " VALUES ('same',2,'n','BLOCK',5,'{}')"))


def test_inactive_old_version_allowed(conn):
    conn.execute(text("INSERT INTO policies (policy_key,version,name,effect,priority,is_active,conditions)"
                      " VALUES ('same2',1,'n','BLOCK',5,false,'{}')"))
    conn.execute(text("INSERT INTO policies (policy_key,version,name,effect,priority,conditions)"
                      " VALUES ('same2',2,'n','BLOCK',5,'{}')"))


def test_payload_hash_must_be_hex64(conn):
    agent = make_agent(conn)
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO actions (agent_id,requested_tool_name,action_type,action_payload,"
                          "payload_hash,idempotency_key) VALUES (:a,'t','FINANCE_PROPOSE_PAYMENT','{}',"
                          "'NOT-A-HASH','k')"), {"a": agent})


def test_idempotency_key_unique_per_agent(conn):
    agent = make_agent(conn)
    make_action(conn, agent, "k1")
    with pytest.raises(IntegrityError):
        make_action(conn, agent, "k1")


def test_same_key_allowed_for_different_agents(conn):
    make_action(conn, make_agent(conn), "shared")
    make_action(conn, make_agent(conn), "shared")


def test_risk_assessment_needs_known_model_version(conn):
    action = make_action(conn)
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO risk_assessments (risk_assessment_id,action_id,risk_score,"
                          "risk_level,confidence_score,risk_source,model_version,features,latency_ms)"
                          " VALUES (:i,:a,0.5,'MEDIUM',0.9,'HEURISTIC_FALLBACK','nope','{}',1)"),
                     {"i": uuid.uuid4(), "a": action})


def test_risk_score_range(conn):
    conn.execute(text("INSERT INTO model_versions (model_version,model_kind,algorithm,feature_schema_version)"
                      " VALUES ('heuristic-v1','HEURISTIC_FALLBACK','rules','1')"))
    action = make_action(conn)
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO risk_assessments (risk_assessment_id,action_id,risk_score,"
                          "risk_level,confidence_score,risk_source,model_version,features,latency_ms)"
                          " VALUES (:i,:a,1.5,'HIGH',0.9,'HEURISTIC_FALLBACK','heuristic-v1','{}',1)"),
                     {"i": uuid.uuid4(), "a": action})


def test_only_one_active_model_per_kind(conn):
    conn.execute(text("INSERT INTO model_versions (model_version,model_kind,algorithm,feature_schema_version,"
                      "is_active) VALUES ('m1','ML_MODEL','lr','1',true)"))
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO model_versions (model_version,model_kind,algorithm,"
                          "feature_schema_version,is_active) VALUES ('m2','ML_MODEL','lr','1',true)"))


def test_decision_sequence_unique_per_action(conn):
    action = make_action(conn)
    make_decision(conn, action, 1)
    make_decision(conn, action, 2)
    with pytest.raises(IntegrityError):
        make_decision(conn, action, 2)


def _approval(conn, status, reviewer=None, reviewed_at=None, consumed_at=None):
    action = make_action(conn)
    decision = make_decision(conn, action)
    return conn.execute(text(
        "INSERT INTO approval_requests (action_id,governance_decision_id,approval_status,payload_hash,"
        "expires_at,reviewed_by_user_id,reviewed_at,consumed_at) VALUES (:a,:d,:s,:h,now()+interval '1 hour',"
        ":r,:ra,:c)"), {"a": action, "d": decision, "s": status, "h": HASH, "r": reviewer,
                        "ra": reviewed_at, "c": consumed_at})


def test_pending_approval_without_reviewer_ok(conn):
    _approval(conn, "PENDING")


def test_approved_requires_reviewer(conn):
    with pytest.raises(IntegrityError):
        _approval(conn, "APPROVED")


def test_approved_with_reviewer_ok(conn):
    user = make_user(conn)
    action = make_action(conn)
    decision = make_decision(conn, action)
    conn.execute(text("INSERT INTO approval_requests (action_id,governance_decision_id,approval_status,"
                      "payload_hash,expires_at,reviewed_by_user_id,reviewed_at) VALUES (:a,:d,'APPROVED',:h,"
                      "now()+interval '1 hour',:u,now())"), {"a": action, "d": decision, "h": HASH, "u": user})


def test_consumed_only_when_approved(conn):
    action = make_action(conn)
    decision = make_decision(conn, action)
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO approval_requests (action_id,governance_decision_id,approval_status,"
                          "payload_hash,expires_at,consumed_at) VALUES (:a,:d,'PENDING',:h,"
                          "now()+interval '1 hour',now())"), {"a": action, "d": decision, "h": HASH})


def test_one_approval_per_decision(conn):
    action = make_action(conn)
    decision = make_decision(conn, action)
    sql = ("INSERT INTO approval_requests (action_id,governance_decision_id,payload_hash,expires_at)"
           " VALUES (:a,:d,:h,now()+interval '1 hour')")
    conn.execute(text(sql), {"a": action, "d": decision, "h": HASH})
    with pytest.raises(IntegrityError):
        conn.execute(text(sql), {"a": action, "d": decision, "h": HASH})


def _execution(conn, status, attempt=1, **cols):
    action = make_action(conn)
    decision = make_decision(conn, action)
    fields = {"action_id": action, "governance_decision_id": decision,
              "attempt_number": attempt, "execution_status": status, **cols}
    names = ",".join(fields)
    values = ",".join(f":{k}" for k in fields)
    conn.execute(text(f"INSERT INTO executions ({names}) VALUES ({values})"), fields)


def test_pending_execution_ok(conn):
    _execution(conn, "PENDING")


def test_succeeded_needs_times(conn):
    with pytest.raises(IntegrityError):
        _execution(conn, "SUCCEEDED")


def test_failed_needs_error_code(conn):
    with pytest.raises(IntegrityError):
        _execution(conn, "FAILED")


def test_failed_with_error_code_ok(conn):
    _execution(conn, "FAILED", error_code="TOOL_EXECUTION_FAILED")


def test_blocked_must_not_have_started(conn):
    with pytest.raises(IntegrityError):
        _execution(conn, "BLOCKED", started_at=datetime.now(timezone.utc))


def test_blocked_without_start_ok(conn):
    _execution(conn, "BLOCKED")


def test_attempt_number_positive(conn):
    with pytest.raises(IntegrityError):
        _execution(conn, "PENDING", attempt=0)


def test_audit_event_enum_check(conn):
    with pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO audit_events (event_name,actor_type,outcome) "
                          "VALUES ('MADE_UP','SYSTEM','SUCCESS')"))


def test_audit_event_insert_ok(conn):
    conn.execute(text("INSERT INTO audit_events (event_name,actor_type,outcome) "
                      "VALUES ('ACTION_SUBMITTED','SYSTEM','SUCCESS')"))


# --- migration 0002: append-only triggers --------------------------------------------------

@pytest.mark.parametrize("sql", [
    "UPDATE actions SET requested_tool_name='changed'",
    "DELETE FROM actions",
    "UPDATE audit_events SET outcome='FAILURE'",
    "DELETE FROM audit_events",
    "UPDATE governance_decisions SET final_decision='BLOCK'",
    "DELETE FROM governance_decisions",
    "UPDATE risk_assessments SET risk_level='LOW'",
    "DELETE FROM risk_assessments",
    "UPDATE evaluation_results SET sample_size=1",
    "DELETE FROM evaluation_results",
])
def test_immutable_tables_reject_update_and_delete(conn, sql):
    action = make_action(conn)
    make_decision(conn, action)
    conn.execute(text("INSERT INTO audit_events (event_name,actor_type,outcome) "
                      "VALUES ('ACTION_SUBMITTED','SYSTEM','SUCCESS')"))
    conn.execute(text("INSERT INTO model_versions (model_version,model_kind,algorithm,feature_schema_version)"
                      " VALUES ('hv','HEURISTIC_FALLBACK','r','1')"))
    conn.execute(text("INSERT INTO risk_assessments (risk_assessment_id,action_id,risk_score,risk_level,"
                      "confidence_score,risk_source,model_version,features,latency_ms) VALUES (:i,:a,0.1,'LOW',"
                      "0.9,'HEURISTIC_FALLBACK','hv','{}',1)"), {"i": uuid.uuid4(), "a": action})
    conn.execute(text("INSERT INTO evaluation_results (evaluation_type,sample_size,metrics,started_at,"
                      "completed_at) VALUES ('PRODUCTION_RECORDS',1,'{}',now(),now())"))
    with pytest.raises(DBAPIError) as exc:
        conn.execute(text(sql))
    assert "append-only" in str(exc.value)


def test_mutable_tables_can_still_be_updated(conn):
    agent = make_agent(conn)
    conn.execute(text("UPDATE agents SET agent_status='DISABLED' WHERE agent_id=:a"), {"a": agent})


# --- migrations up and down ----------------------------------------------------------------

def test_downgrade_then_upgrade_again(engine):
    down = run_alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr
    with engine.connect() as c:
        left = {r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    assert not (EXPECTED_TABLES & left)
    up = run_alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
