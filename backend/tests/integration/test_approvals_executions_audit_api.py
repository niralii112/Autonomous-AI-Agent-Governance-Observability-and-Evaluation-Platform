"""APR-01..05, EXE-01..02 and AUD-01..02 over HTTP, checked against the contract examples."""

import json
import uuid
from pathlib import Path

import pytest

from app.schemas import (
    ApprovalDecisionResponse, ApprovalResponse, ApprovalResponsePage, AuditEventResponse, AuditEventResponsePage,
    ExecutionResponse, ExecutionResponsePage,
)
from tests.integration.api_support import audit_rows, client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL
from tests.integration.flow_support import pay_body, risk, session_factory, tools, world  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
UNKNOWN = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def finance_id(db, world):
    return db("SELECT agent_id FROM agents WHERE agent_name='finance-agent-01'")[0]["agent_id"]


async def held(client, make_user, finance_id, amount=5000, name="ops"):
    h = await headers_for(client, make_user, name, "OPERATOR")
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, amount), headers=h)
    assert r.status_code == 200, r.text
    return h, r.json()


# ============================================================================================== approvals

@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER", "OPERATOR", "VIEWER"])
async def test_every_role_can_read_approvals(client, make_user, finance_id, tools, risk, role):
    _, body = await held(client, make_user, finance_id)
    h = await headers_for(client, make_user, "reader", role)
    assert (await client.get("/api/v1/approvals", headers=h)).status_code == 200
    assert (await client.get(f"/api/v1/approvals/{body['approval']['approval_id']}", headers=h)).status_code == 200


async def test_approvals_need_login(client):
    assert (await client.get("/api/v1/approvals")).status_code == 401
    assert (await client.post(f"/api/v1/approvals/{UNKNOWN}/approve", json={})).status_code == 401


async def test_list_and_get_match_the_contract(client, make_user, finance_id, tools, risk):
    ops, body = await held(client, make_user, finance_id)
    r = await client.get("/api/v1/approvals", headers=ops)
    page = ApprovalResponsePage.model_validate(r.json())
    assert page.total_items == 1 and page.items[0].approval_id == uuid.UUID(body["approval"]["approval_id"])
    assert page.items[0].action_summary is not None
    one = await client.get(f"/api/v1/approvals/{body['approval']['approval_id']}", headers=ops)
    ApprovalResponse.model_validate(one.json())
    example = json.loads((EXAMPLES / "APR-02.response.json").read_text())
    assert set(one.json()) == set(example)


async def test_list_filters_and_sorting(client, make_user, finance_id, tools, risk, db):
    ops, first = await held(client, make_user, finance_id, 5000)
    _, second = await held(client, make_user, finance_id, 5001, name="ops2")
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    await client.post(f"/api/v1/approvals/{first['approval']['approval_id']}/reject", json={"review_comment": "no"}, headers=reviewer)

    pending = (await client.get("/api/v1/approvals?approval_status=PENDING", headers=ops)).json()
    assert [i["approval_id"] for i in pending["items"]] == [second["approval"]["approval_id"]]
    rejected = (await client.get("/api/v1/approvals?approval_status=REJECTED", headers=ops)).json()
    assert rejected["total_items"] == 1
    by_agent = (await client.get(f"/api/v1/approvals?agent_id={uuid.uuid4()}", headers=ops)).json()
    assert by_agent["items"] == [] and by_agent["total_pages"] == 0
    asc = (await client.get("/api/v1/approvals?sort_by=expires_at&sort_order=asc", headers=ops)).json()
    assert len(asc["items"]) == 2
    assert (await client.get("/api/v1/approvals?sort_by=nonsense", headers=ops)).status_code == 422
    assert (await client.get("/api/v1/approvals?page_size=101", headers=ops)).status_code == 422
    assert (await client.get("/api/v1/approvals?approval_status=NOPE", headers=ops)).status_code == 422


async def test_unknown_approval_is_404(client, make_user):
    h = await headers_for(client, make_user, "someone", "VIEWER")
    r = await client.get(f"/api/v1/approvals/{UNKNOWN}", headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"


async def test_apr03_approve_runs_the_action(client, make_user, finance_id, tools, risk, db):
    _, body = await held(client, make_user, finance_id)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    r = await client.post(f"/api/v1/approvals/{body['approval']['approval_id']}/approve",
                          json={"review_comment": "Verified"}, headers=reviewer)
    assert r.status_code == 200, r.text
    out = ApprovalDecisionResponse.model_validate(r.json())
    assert out.approval.approval_status.value == "APPROVED" and out.execution.execution_status.value == "SUCCEEDED"
    assert len(tools["payment_processor_sim"].calls) == 1


async def test_apr03_approve_works_without_a_body(client, make_user, finance_id, tools, risk):
    _, body = await held(client, make_user, finance_id)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    r = await client.post(f"/api/v1/approvals/{body['approval']['approval_id']}/approve", headers=reviewer)
    assert r.status_code == 200, r.text


async def test_apr03_replay_is_409(client, make_user, finance_id, tools, risk):
    _, body = await held(client, make_user, finance_id)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    url = f"/api/v1/approvals/{body['approval']['approval_id']}/approve"
    assert (await client.post(url, json={}, headers=reviewer)).status_code == 200
    r = await client.post(url, json={}, headers=reviewer)
    assert r.status_code == 409 and r.json()["error_code"] == "APPROVAL_NOT_PENDING"
    assert len(tools["payment_processor_sim"].calls) == 1


async def test_apr03_wrong_role_is_403_and_audited(client, make_user, finance_id, tools, risk, db):
    _, body = await held(client, make_user, finance_id)
    viewer = await headers_for(client, make_user, "viewer1", "VIEWER")
    r = await client.post(f"/api/v1/approvals/{body['approval']['approval_id']}/approve", json={}, headers=viewer)
    assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"
    assert len(audit_rows(db, "APPROVAL_DENIED_UNAUTHORIZED")) == 1  # a router-level role check would have lost this row
    assert tools["payment_processor_sim"].calls == []


async def test_apr03_submitter_cannot_approve_their_own_action(client, make_user, finance_id, tools, risk, db):
    admin = await headers_for(client, make_user, "boss", "ADMIN")
    r = await client.post("/api/v1/actions", json=pay_body(finance_id, 5000), headers=admin)
    approval_id = r.json()["approval"]["approval_id"]
    r = await client.post(f"/api/v1/approvals/{approval_id}/approve", json={}, headers=admin)
    assert r.status_code == 403 and r.json()["error_code"] == "SELF_APPROVAL_FORBIDDEN"


async def test_apr04_reject_needs_a_comment(client, make_user, finance_id, tools, risk):
    _, body = await held(client, make_user, finance_id)
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    url = f"/api/v1/approvals/{body['approval']['approval_id']}/reject"
    for bad in ({}, {"review_comment": ""}):
        r = await client.post(url, json=bad, headers=reviewer)
        assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"
    r = await client.post(url, json={"review_comment": "Amount mismatch"}, headers=reviewer)
    assert r.status_code == 200 and r.json()["execution"] is None
    assert r.json()["approval"]["approval_status"] == "REJECTED" and tools["payment_processor_sim"].calls == []


async def test_apr05_cancel(client, make_user, finance_id, tools, risk):
    ops, body = await held(client, make_user, finance_id)
    url = f"/api/v1/approvals/{body['approval']['approval_id']}/cancel"
    reviewer = await headers_for(client, make_user, "rev1", "REVIEWER")
    assert (await client.post(url, headers=reviewer)).status_code == 403  # REVIEWER may not cancel
    r = await client.post(url, headers=ops)
    assert r.status_code == 200 and r.json()["approval"]["approval_status"] == "CANCELLED"
    r = await client.post(url, headers=ops)
    assert r.status_code == 409 and r.json()["error_code"] == "APPROVAL_NOT_PENDING"


async def test_unknown_approval_actions_are_404(client, make_user):
    admin = await headers_for(client, make_user, "boss", "ADMIN")
    for path, body in (("approve", {}), ("reject", {"review_comment": "x"}), ("cancel", None)):
        r = await client.post(f"/api/v1/approvals/{UNKNOWN}/{path}", json=body, headers=admin) if body is not None \
            else await client.post(f"/api/v1/approvals/{UNKNOWN}/{path}", headers=admin)
        assert r.status_code == 404, (path, r.text)


# ============================================================================================== executions

async def test_exe01_and_exe02(client, make_user, finance_id, tools, risk):
    ops, body = await held(client, make_user, finance_id, 450)  # ALLOW: executed at once
    execution_id = body["execution"]["execution_id"]
    page = ExecutionResponsePage.model_validate((await client.get("/api/v1/executions", headers=ops)).json())
    assert page.total_items == 1 and str(page.items[0].execution_id) == execution_id
    one = await client.get(f"/api/v1/executions/{execution_id}", headers=ops)
    ExecutionResponse.model_validate(one.json())
    assert set(one.json()) == set(json.loads((EXAMPLES / "EXE-02.response.json").read_text()))
    assert (await client.get(f"/api/v1/executions/{UNKNOWN}", headers=ops)).status_code == 404


async def test_exe01_filters(client, make_user, finance_id, tools, risk):
    ops, body = await held(client, make_user, finance_id, 450)
    action_id = body["action"]["action_id"]
    q = lambda s: client.get(f"/api/v1/executions?{s}", headers=ops)  # noqa: E731
    assert (await q("execution_status=SUCCEEDED")).json()["total_items"] == 1
    assert (await q("execution_status=FAILED")).json()["total_items"] == 0
    assert (await q(f"action_id={action_id}")).json()["total_items"] == 1
    assert (await q(f"agent_id={finance_id}")).json()["total_items"] == 1
    assert (await q(f"agent_id={uuid.uuid4()}")).json()["total_items"] == 0
    assert (await q("created_from=2999-01-01T00:00:00Z")).json()["total_items"] == 0
    assert (await q("sort_by=latency_ms&sort_order=asc")).status_code == 200
    assert (await q("sort_by=other")).status_code == 422
    assert (await client.get("/api/v1/executions")).status_code == 401


# ============================================================================================== audit events

async def test_aud01_and_aud02_for_admin_and_reviewer(client, make_user, finance_id, tools, risk):
    ops, _ = await held(client, make_user, finance_id, 450)
    for role in ("ADMIN", "REVIEWER"):
        h = await headers_for(client, make_user, f"aud-{role.lower()}", role)
        page = AuditEventResponsePage.model_validate((await client.get("/api/v1/audit-events", headers=h)).json())
        assert page.total_items >= 3
        event = page.items[0]
        one = await client.get(f"/api/v1/audit-events/{event.audit_event_id}", headers=h)
        AuditEventResponse.model_validate(one.json())
        assert set(one.json()) == set(json.loads((EXAMPLES / "AUD-02.response.json").read_text()))


@pytest.mark.parametrize("role", ["OPERATOR", "VIEWER"])
async def test_the_audit_log_is_closed_to_operator_and_viewer(client, make_user, role):
    h = await headers_for(client, make_user, "nosy", role)
    for url in ("/api/v1/audit-events", f"/api/v1/audit-events/{UNKNOWN}"):
        r = await client.get(url, headers=h)
        assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"
    assert (await client.get("/api/v1/audit-events")).status_code == 401


async def test_aud01_filters(client, make_user, finance_id, tools, risk):
    ops, body = await held(client, make_user, finance_id, 450)
    admin = await headers_for(client, make_user, "boss", "ADMIN")
    q = lambda s: client.get(f"/api/v1/audit-events?{s}", headers=admin)  # noqa: E731
    only = (await q("event_name=EXECUTION_SUCCEEDED")).json()
    assert only["total_items"] == 1 and only["items"][0]["event_name"] == "EXECUTION_SUCCEEDED"
    assert (await q(f"action_id={body['action']['action_id']}")).json()["total_items"] >= 4
    assert (await q(f"action_id={uuid.uuid4()}")).json()["total_items"] == 0
    assert (await q("actor_type=SYSTEM")).json()["total_items"] >= 1
    assert (await q("outcome=DENIED")).json()["total_items"] == 0
    asc = (await q("sort_order=asc&page_size=100")).json()["items"]
    assert [e["created_at"] for e in asc] == sorted(e["created_at"] for e in asc)
    assert (await q("event_name=NOT_AN_EVENT")).status_code == 422
    assert (await q("sort_by=event_name")).status_code == 422


async def test_aud02_unknown_is_404(client, make_user):
    admin = await headers_for(client, make_user, "boss", "ADMIN")
    r = await client.get(f"/api/v1/audit-events/{UNKNOWN}", headers=admin)
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_the_audit_log_has_no_write_route():
    from app.main import create_app
    methods = {m for r in create_app().routes if r.path.startswith("/api/v1/audit-events") for m in r.methods}
    assert methods <= {"GET", "HEAD"}
