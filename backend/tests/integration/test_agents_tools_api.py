"""AGT-01..06 and TLS-01..04 through the real app and a real PostgreSQL database."""

import json
import uuid
from pathlib import Path

import pytest

from app.schemas import (
    AgentResponse, AgentResponsePage, ToolPermissionListResponse, ToolResponse, ToolResponsePage,
)
from tests.integration.api_support import (  # noqa: F401  (fixtures are used by name)
    audit_rows, auth, client, db, env, headers_for, make_user, token_of,
)
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


async def admin(client, make_user):
    return await headers_for(client, make_user, "boss", "ADMIN")


async def new_tool(client, h, name="payment_processor_sim", action="FINANCE_PROPOSE_PAYMENT", sens="WRITE"):
    r = await client.post("/api/v1/tools", json={"tool_name": name, "tool_sensitivity": sens,
                                                  "supported_action_type": action}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def new_agent(client, h, name="finance-agent-01", category="FINANCE", **extra):
    r = await client.post("/api/v1/agents", json={"agent_name": name, "agent_category": category, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


# ======================================= access control ===========================================

@pytest.mark.parametrize("role", ["REVIEWER", "OPERATOR", "VIEWER"])
async def test_only_admin_can_write_registries(client, make_user, role):
    admin_h = await admin(client, make_user)
    agent, tool = await new_agent(client, admin_h), await new_tool(client, admin_h)
    h = await headers_for(client, make_user, "someone", role)
    calls = [
        client.post("/api/v1/agents", json={"agent_name": "abc", "agent_category": "FINANCE"}, headers=h),
        client.patch(f"/api/v1/agents/{agent['agent_id']}", json={"trust_tier": 3}, headers=h),
        client.put(f"/api/v1/agents/{agent['agent_id']}/tool-permissions", json={"permissions": []}, headers=h),
        client.post("/api/v1/tools", json={"tool_name": "x", "tool_sensitivity": "READ_ONLY",
                                           "supported_action_type": "FINANCE_GET_REPORT"}, headers=h),
        client.patch(f"/api/v1/tools/{tool['tool_id']}", json={"tool_status": "DISABLED"}, headers=h),
    ]
    for call in calls:
        r = await call
        assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER", "OPERATOR", "VIEWER"])
async def test_every_logged_in_role_can_read(client, make_user, role):
    admin_h = await admin(client, make_user)
    agent, tool = await new_agent(client, admin_h), await new_tool(client, admin_h)
    h = await headers_for(client, make_user, "reader", role)
    for path in ("/api/v1/agents", f"/api/v1/agents/{agent['agent_id']}", f"/api/v1/agents/{agent['agent_id']}/tool-permissions",
                 "/api/v1/tools", f"/api/v1/tools/{tool['tool_id']}"):
        assert (await client.get(path, headers=h)).status_code == 200, path


async def test_registries_need_login(client):
    for method, path in [("get", "/api/v1/agents"), ("post", "/api/v1/agents"), ("get", "/api/v1/tools"),
                         ("get", f"/api/v1/agents/{UNKNOWN_ID}/tool-permissions")]:
        r = await getattr(client, method)(path)
        assert r.status_code == 401, path


# ======================================= AGT-01 / AGT-03 / AGT-04 =================================

async def test_create_agent_matches_the_contract_example(client, make_user, db):
    h = await admin(client, make_user)
    example = json.loads((EXAMPLES / "AGT-01.request.json").read_text())
    r = await client.post("/api/v1/agents", json=example, headers=h)
    assert r.status_code == 201
    agent = AgentResponse.model_validate(r.json())
    assert agent.agent_status.value == "ACTIVE" and agent.trust_tier == 2 and agent.owner_user_id is None
    assert set(r.json()) == set(json.loads((EXAMPLES / "AGT-01.response.json").read_text()))
    event = audit_rows(db, "AGENT_REGISTERED")[0]
    assert str(event["agent_id"]) == r.json()["agent_id"] and event["event_data"]["agent_name"] == "finance-agent-01"


async def test_create_agent_with_owner_and_description(client, make_user):
    h = await admin(client, make_user)
    owner = make_user("owner", "OPERATOR")
    a = await new_agent(client, h, description="Pays invoices", trust_tier=3, owner_user_id=str(owner))
    assert a["description"] == "Pays invoices" and a["trust_tier"] == 3 and a["owner_user_id"] == str(owner)


async def test_duplicate_agent_name_is_409(client, make_user):
    h = await admin(client, make_user)
    await new_agent(client, h)
    r = await client.post("/api/v1/agents", json={"agent_name": "finance-agent-01", "agent_category": "FINANCE"}, headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "DUPLICATE_RESOURCE"


@pytest.mark.parametrize("body", [
    {"agent_name": "Finance_Agent", "agent_category": "FINANCE"},   # not kebab-case
    {"agent_name": "1st-agent", "agent_category": "FINANCE"},        # must start with a letter
    {"agent_name": "ab", "agent_category": "FINANCE"},               # too short
    {"agent_name": "a" * 101, "agent_category": "FINANCE"},          # too long
    {"agent_name": "good-name", "agent_category": "PIRATE"},         # unknown category
    {"agent_name": "good-name", "agent_category": "FINANCE", "trust_tier": 0},
    {"agent_name": "good-name", "agent_category": "FINANCE", "trust_tier": 4},
    {"agent_name": "good-name"},                                     # category missing
    {"agent_name": "good-name", "agent_category": "FINANCE", "surprise": 1},
])
async def test_create_agent_validation(client, make_user, body):
    h = await admin(client, make_user)
    r = await client.post("/api/v1/agents", json=body, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_unknown_owner_is_422(client, make_user):
    h = await admin(client, make_user)
    r = await client.post("/api/v1/agents", json={"agent_name": "good-name", "agent_category": "FINANCE",
                                                  "owner_user_id": UNKNOWN_ID}, headers=h)
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "owner_user_id"


async def test_get_agent_and_404(client, make_user):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    assert (await client.get(f"/api/v1/agents/{a['agent_id']}", headers=h)).json()["agent_name"] == "finance-agent-01"
    r = await client.get(f"/api/v1/agents/{UNKNOWN_ID}", headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"
    assert (await client.get("/api/v1/agents/not-a-uuid", headers=h)).status_code == 422


async def test_update_agent_fields_and_audit(client, make_user, db):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    r = await client.patch(f"/api/v1/agents/{a['agent_id']}",
                           json={"description": "new text", "agent_status": "DISABLED", "trust_tier": 1}, headers=h)
    assert r.status_code == 200
    body = AgentResponse.model_validate(r.json())
    assert (body.description, body.agent_status.value, body.trust_tier) == ("new text", "DISABLED", 1)
    event = audit_rows(db, "AGENT_UPDATED")[0]["event_data"]
    assert event["changed_fields"] == ["description", "agent_status", "trust_tier"]
    assert (event["status_from"], event["status_to"], event["trust_tier_from"], event["trust_tier_to"]) == ("ACTIVE", "DISABLED", 2, 1)


async def test_explicit_null_description_clears_it_but_null_status_is_ignored(client, make_user):
    h = await admin(client, make_user)
    a = await new_agent(client, h, description="something")
    r = await client.patch(f"/api/v1/agents/{a['agent_id']}", json={"description": None, "agent_status": None}, headers=h)
    assert r.json()["description"] is None and r.json()["agent_status"] == "ACTIVE"


async def test_empty_or_unchanged_agent_update_logs_nothing(client, make_user, db):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    for body in ({}, {"trust_tier": 2, "agent_status": "ACTIVE"}):
        assert (await client.patch(f"/api/v1/agents/{a['agent_id']}", json=body, headers=h)).status_code == 200
    assert audit_rows(db, "AGENT_UPDATED") == []


@pytest.mark.parametrize("body", [{"trust_tier": 9}, {"agent_status": "GONE"}, {"agent_name": "renamed"}, {"description": "x" * 1001}])
async def test_update_agent_validation(client, make_user, body):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    assert (await client.patch(f"/api/v1/agents/{a['agent_id']}", json=body, headers=h)).status_code == 422


async def test_update_unknown_agent_is_404(client, make_user):
    h = await admin(client, make_user)
    assert (await client.patch(f"/api/v1/agents/{UNKNOWN_ID}", json={"trust_tier": 1}, headers=h)).status_code == 404


# ======================================= AGT-02 list ==============================================

async def test_list_agents_filters_paging_and_sorting(client, make_user):
    h = await admin(client, make_user)
    for name, cat in [("alpha-agent", "FINANCE"), ("bravo-agent", "FINANCE"), ("charlie-agent", "CUSTOMER_SUPPORT")]:
        await new_agent(client, h, name, cat)
    disabled = (await client.get("/api/v1/agents", params={"sort_by": "agent_name", "sort_order": "asc"}, headers=h)).json()["items"][1]
    await client.patch(f"/api/v1/agents/{disabled['agent_id']}", json={"agent_status": "DISABLED"}, headers=h)

    page = AgentResponsePage.model_validate((await client.get(
        "/api/v1/agents", params={"sort_by": "agent_name", "sort_order": "asc", "page_size": 2}, headers=h)).json())
    assert [a.agent_name for a in page.items] == ["alpha-agent", "bravo-agent"]
    assert (page.total_items, page.total_pages) == (3, 2)
    fin = (await client.get("/api/v1/agents", params={"agent_category": "FINANCE"}, headers=h)).json()
    assert fin["total_items"] == 2
    off = (await client.get("/api/v1/agents", params={"agent_status": "DISABLED"}, headers=h)).json()
    assert [a["agent_name"] for a in off["items"]] == ["bravo-agent"]


@pytest.mark.parametrize("params", [{"sort_by": "trust_tier"}, {"page_size": 101}, {"page": 0}, {"agent_category": "X"}])
async def test_list_agents_rejects_bad_query(client, make_user, params):
    h = await admin(client, make_user)
    assert (await client.get("/api/v1/agents", params=params, headers=h)).status_code == 422


# ======================================= tools ====================================================

async def test_create_tool_matches_the_contract_example(client, make_user, db):
    h = await admin(client, make_user)
    r = await client.post("/api/v1/tools", json=json.loads((EXAMPLES / "TLS-01.request.json").read_text()), headers=h)
    assert r.status_code == 201
    tool = ToolResponse.model_validate(r.json())
    assert tool.tool_status.value == "ACTIVE"
    assert set(r.json()) == set(json.loads((EXAMPLES / "TLS-01.response.json").read_text()))
    event = audit_rows(db, "TOOL_REGISTERED")[0]["event_data"]
    assert event["tool_name"] == "payment_processor_sim" and event["supported_action_type"] == "FINANCE_PROPOSE_PAYMENT"


async def test_duplicate_tool_name_and_second_tool_for_same_action_type_are_409(client, make_user):
    h = await admin(client, make_user)
    await new_tool(client, h)
    same_name = await client.post("/api/v1/tools", json={"tool_name": "payment_processor_sim", "tool_sensitivity": "WRITE",
                                                         "supported_action_type": "SUPPORT_PROPOSE_REFUND"}, headers=h)
    same_type = await client.post("/api/v1/tools", json={"tool_name": "other_payment_tool", "tool_sensitivity": "WRITE",
                                                         "supported_action_type": "FINANCE_PROPOSE_PAYMENT"}, headers=h)
    for r in (same_name, same_type):
        assert r.status_code == 409 and r.json()["error_code"] == "DUPLICATE_RESOURCE"
    assert same_name.json()["details"][0]["field"] == "tool_name"
    assert same_type.json()["details"][0]["field"] == "supported_action_type"


@pytest.mark.parametrize("body", [
    {"tool_name": "Payment-Tool", "tool_sensitivity": "WRITE", "supported_action_type": "FINANCE_PROPOSE_PAYMENT"},
    {"tool_name": "9tool", "tool_sensitivity": "WRITE", "supported_action_type": "FINANCE_PROPOSE_PAYMENT"},
    {"tool_name": "", "tool_sensitivity": "WRITE", "supported_action_type": "FINANCE_PROPOSE_PAYMENT"},
    {"tool_name": "ok_tool", "tool_sensitivity": "SECRET", "supported_action_type": "FINANCE_PROPOSE_PAYMENT"},
    {"tool_name": "ok_tool", "tool_sensitivity": "WRITE", "supported_action_type": "MAKE_COFFEE"},
    {"tool_name": "ok_tool", "tool_sensitivity": "WRITE"},
])
async def test_create_tool_validation(client, make_user, body):
    h = await admin(client, make_user)
    r = await client.post("/api/v1/tools", json=body, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_update_tool_status_and_description(client, make_user, db):
    h = await admin(client, make_user)
    t = await new_tool(client, h)
    r = await client.patch(f"/api/v1/tools/{t['tool_id']}", json={"tool_status": "DISABLED", "description": "off"}, headers=h)
    assert r.status_code == 200 and (r.json()["tool_status"], r.json()["description"]) == ("DISABLED", "off")
    event = audit_rows(db, "TOOL_UPDATED")[0]["event_data"]
    assert event["changed_fields"] == ["description", "tool_status"] and event["status_to"] == "DISABLED"


async def test_sensitivity_and_action_type_cannot_be_changed(client, make_user):
    h = await admin(client, make_user)
    t = await new_tool(client, h)
    r = await client.patch(f"/api/v1/tools/{t['tool_id']}", json={"tool_sensitivity": "READ_ONLY"}, headers=h)
    assert r.status_code == 422
    assert (await client.get(f"/api/v1/tools/{t['tool_id']}", headers=h)).json()["tool_sensitivity"] == "WRITE"


async def test_get_update_unknown_tool_is_404(client, make_user):
    h = await admin(client, make_user)
    assert (await client.get(f"/api/v1/tools/{UNKNOWN_ID}", headers=h)).status_code == 404
    assert (await client.patch(f"/api/v1/tools/{UNKNOWN_ID}", json={"tool_status": "DISABLED"}, headers=h)).status_code == 404


async def test_empty_tool_update_logs_nothing(client, make_user, db):
    h = await admin(client, make_user)
    t = await new_tool(client, h)
    assert (await client.patch(f"/api/v1/tools/{t['tool_id']}", json={}, headers=h)).status_code == 200
    assert audit_rows(db, "TOOL_UPDATED") == []


async def test_list_tools_filters_paging_sorting(client, make_user):
    h = await admin(client, make_user)
    await new_tool(client, h, "ticket_reader", "SUPPORT_GET_TICKET", "READ_ONLY")
    await new_tool(client, h, "payment_processor_sim", "FINANCE_PROPOSE_PAYMENT", "WRITE")
    await new_tool(client, h, "refund_processor_sim", "SUPPORT_PROPOSE_REFUND", "WRITE")
    page = ToolResponsePage.model_validate((await client.get(
        "/api/v1/tools", params={"sort_by": "tool_name", "sort_order": "asc", "page_size": 2}, headers=h)).json())
    assert [t.tool_name for t in page.items] == ["payment_processor_sim", "refund_processor_sim"] and page.total_pages == 2
    writes = (await client.get("/api/v1/tools", params={"tool_sensitivity": "WRITE"}, headers=h)).json()
    assert writes["total_items"] == 2
    tid = (await client.get("/api/v1/tools", params={"tool_sensitivity": "READ_ONLY"}, headers=h)).json()["items"][0]["tool_id"]
    await client.patch(f"/api/v1/tools/{tid}", json={"tool_status": "DISABLED"}, headers=h)
    assert (await client.get("/api/v1/tools", params={"tool_status": "DISABLED"}, headers=h)).json()["total_items"] == 1


@pytest.mark.parametrize("params", [{"sort_by": "tool_sensitivity"}, {"page_size": 0}, {"tool_sensitivity": "X"}])
async def test_list_tools_rejects_bad_query(client, make_user, params):
    h = await admin(client, make_user)
    assert (await client.get("/api/v1/tools", params=params, headers=h)).status_code == 422


# ======================================= AGT-05 / AGT-06 permissions ===============================

async def setup_two_tools(client, h):
    a = await new_agent(client, h)
    pay = await new_tool(client, h, "payment_processor_sim", "FINANCE_PROPOSE_PAYMENT", "WRITE")
    rep = await new_tool(client, h, "finance_report_reader", "FINANCE_GET_REPORT", "READ_ONLY")
    return a, pay, rep


async def test_new_agent_has_no_permissions(client, make_user):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    r = await client.get(f"/api/v1/agents/{a['agent_id']}/tool-permissions", headers=h)
    assert r.status_code == 200 and r.json() == {"agent_id": a["agent_id"], "permissions": []}


async def test_set_permissions_returns_the_result_and_audits(client, make_user, db):
    h = await admin(client, make_user)
    a, pay, rep = await setup_two_tools(client, h)
    r = await client.put(f"/api/v1/agents/{a['agent_id']}/tool-permissions", headers=h, json={"permissions": [
        {"tool_id": pay["tool_id"], "is_allowed": True}, {"tool_id": rep["tool_id"], "is_allowed": False}]})
    assert r.status_code == 200
    body = ToolPermissionListResponse.model_validate(r.json())
    assert [(p.tool_name, p.is_allowed) for p in body.permissions] == [("finance_report_reader", False), ("payment_processor_sim", True)]
    event = audit_rows(db, "AGENT_UPDATED")[0]["event_data"]
    assert event["granted"] == ["payment_processor_sim"] and event["denied"] == ["finance_report_reader"] and event["removed"] == []
    got = ToolPermissionListResponse.model_validate((await client.get(f"/api/v1/agents/{a['agent_id']}/tool-permissions", headers=h)).json())
    assert got == body


async def test_put_replaces_the_set_and_omitted_tools_lose_access(client, make_user, db):
    h = await admin(client, make_user)
    a, pay, rep = await setup_two_tools(client, h)
    url = f"/api/v1/agents/{a['agent_id']}/tool-permissions"
    await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True},
                                                          {"tool_id": rep["tool_id"], "is_allowed": True}]})
    r = await client.put(url, headers=h, json={"permissions": [{"tool_id": rep["tool_id"], "is_allowed": True}]})
    assert [p["tool_name"] for p in r.json()["permissions"]] == ["finance_report_reader"]
    event = audit_rows(db, "AGENT_UPDATED")[-1]["event_data"]
    assert event["removed"] == ["payment_processor_sim"] and event["granted"] == []


async def test_empty_list_revokes_everything(client, make_user):
    h = await admin(client, make_user)
    a, pay, _ = await setup_two_tools(client, h)
    url = f"/api/v1/agents/{a['agent_id']}/tool-permissions"
    await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True}]})
    assert (await client.put(url, headers=h, json={"permissions": []})).json()["permissions"] == []


async def test_flipping_a_permission_keeps_the_row_and_records_who(client, make_user, db):
    h = await admin(client, make_user)
    boss_id = db("SELECT user_id FROM users WHERE username='boss'")[0]["user_id"]
    a, pay, _ = await setup_two_tools(client, h)
    url = f"/api/v1/agents/{a['agent_id']}/tool-permissions"
    first = (await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True}]})).json()
    second = (await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": False}]})).json()
    assert first["permissions"][0]["permission_id"] == second["permissions"][0]["permission_id"]
    assert second["permissions"][0]["is_allowed"] is False
    assert db("SELECT granted_by_user_id FROM agent_tool_permissions")[0]["granted_by_user_id"] == boss_id


async def test_unchanged_put_logs_nothing(client, make_user, db):
    h = await admin(client, make_user)
    a, pay, _ = await setup_two_tools(client, h)
    url = f"/api/v1/agents/{a['agent_id']}/tool-permissions"
    body = {"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True}]}
    await client.put(url, headers=h, json=body)
    await client.put(url, headers=h, json=body)
    assert len(audit_rows(db, "AGENT_UPDATED")) == 1


async def test_contract_example_for_permissions_is_accepted(client, make_user):
    h = await admin(client, make_user)
    a, pay, _ = await setup_two_tools(client, h)
    example = json.loads((EXAMPLES / "AGT-05.request.json").read_text())
    example["permissions"][0]["tool_id"] = pay["tool_id"]
    r = await client.put(f"/api/v1/agents/{a['agent_id']}/tool-permissions", headers=h, json=example)
    assert r.status_code == 200
    expected = json.loads((EXAMPLES / "AGT-05.response.json").read_text())
    assert set(r.json()) == set(expected) and set(r.json()["permissions"][0]) == set(expected["permissions"][0])


async def test_unknown_or_repeated_tool_is_422_and_changes_nothing(client, make_user):
    h = await admin(client, make_user)
    a, pay, _ = await setup_two_tools(client, h)
    url = f"/api/v1/agents/{a['agent_id']}/tool-permissions"
    await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True}]})
    unknown = await client.put(url, headers=h, json={"permissions": [{"tool_id": UNKNOWN_ID, "is_allowed": True}]})
    repeated = await client.put(url, headers=h, json={"permissions": [{"tool_id": pay["tool_id"], "is_allowed": True},
                                                                       {"tool_id": pay["tool_id"], "is_allowed": False}]})
    for r in (unknown, repeated):
        assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"
    still = (await client.get(url, headers=h)).json()["permissions"]
    assert [(p["tool_name"], p["is_allowed"]) for p in still] == [("payment_processor_sim", True)]


@pytest.mark.parametrize("body", [{}, {"permissions": "all"}, {"permissions": [{"tool_id": "nope", "is_allowed": True}]},
                                  {"permissions": [{"tool_id": UNKNOWN_ID}]}, {"permissions": [], "extra": 1}])
async def test_permission_body_validation(client, make_user, body):
    h = await admin(client, make_user)
    a = await new_agent(client, h)
    assert (await client.put(f"/api/v1/agents/{a['agent_id']}/tool-permissions", headers=h, json=body)).status_code == 422


async def test_permissions_of_unknown_agent_are_404(client, make_user):
    h = await admin(client, make_user)
    assert (await client.get(f"/api/v1/agents/{UNKNOWN_ID}/tool-permissions", headers=h)).status_code == 404
    assert (await client.put(f"/api/v1/agents/{UNKNOWN_ID}/tool-permissions", headers=h, json={"permissions": []})).status_code == 404


# ======================== the services re-check ADMIN themselves (spec: router AND service) ================

@pytest.fixture
async def session():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    async with async_sessionmaker(eng, expire_on_commit=False)() as s:
        yield s
    await eng.dispose()


@pytest.mark.parametrize("role", ["REVIEWER", "OPERATOR", "VIEWER"])
async def test_services_refuse_non_admins_even_if_the_router_is_bypassed(session, role):
    from app.core.enums import AgentCategory, ToolSensitivity, ActionType, UserRole
    from app.core.exceptions import AppError
    from app.schemas import (ActorContext, AgentCreateRequest, AgentUpdateRequest, ToolCreateRequest,
                             ToolPermissionsUpdateRequest, ToolUpdateRequest)
    from app.services import agent_service, tool_service

    actor = ActorContext(user_id=uuid.uuid4(), username="x", role=UserRole(role))
    calls = [
        agent_service.register_agent(session, AgentCreateRequest(agent_name="abc", agent_category=AgentCategory.FINANCE), actor),
        agent_service.update_agent(session, uuid.uuid4(), AgentUpdateRequest(trust_tier=3), actor),
        agent_service.set_tool_permissions(session, uuid.uuid4(), ToolPermissionsUpdateRequest(permissions=[]), actor),
        tool_service.register_tool(session, ToolCreateRequest(tool_name="t", tool_sensitivity=ToolSensitivity.READ_ONLY,
                                                              supported_action_type=ActionType.FINANCE_GET_REPORT), actor),
        tool_service.update_tool(session, uuid.uuid4(), ToolUpdateRequest(), actor),
    ]
    for call in calls:
        with pytest.raises(AppError) as e:
            await call
        assert e.value.error_code.value == "AUTH_INSUFFICIENT_ROLE"
