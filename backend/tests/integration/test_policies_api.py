"""POL-01..05 through the real app and a real PostgreSQL database."""

import asyncio
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas import PolicyResponse, PolicyResponsePage
from tests.integration.api_support import (  # noqa: F401  (fixtures are used by name)
    audit_rows, client, db, env, headers_for, make_user, token_of,
)
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
BIG_PAYMENT = {"all": [{"field": "action_type", "operator": "EQ", "value": "FINANCE_PROPOSE_PAYMENT"},
                       {"field": "payload.amount", "operator": "GT", "value": 50000}], "any": []}


def body(key="block-big-payment", effect="BLOCK", priority=10, mandatory=False, conditions=None, **extra):
    return {"policy_key": key, "name": key.replace("-", " "), "effect": effect, "priority": priority,
            "is_mandatory": mandatory, "conditions": conditions or BIG_PAYMENT, **extra}


def version_body(effect="HUMAN_REVIEW", priority=20, mandatory=False, conditions=None, **extra):
    return {"name": "v-next", "effect": effect, "priority": priority, "is_mandatory": mandatory,
            "conditions": conditions or BIG_PAYMENT, **extra}


async def admin(client, make_user):
    return await headers_for(client, make_user, "boss", "ADMIN")


async def new_policy(client, h, **kw):
    r = await client.post("/api/v1/policies", json=body(**kw), headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def active_versions(db, key):
    return [r["version"] for r in db("SELECT version FROM policies WHERE policy_key=:k AND is_active ORDER BY version", k=key)]


# ======================================= access control ===========================================

@pytest.mark.parametrize("role", ["REVIEWER", "OPERATOR", "VIEWER"])
async def test_only_admin_can_write_policies(client, make_user, role):
    a = await admin(client, make_user)
    p = await new_policy(client, a)
    h = await headers_for(client, make_user, "someone", role)
    calls = [client.post("/api/v1/policies", json=body("another-one"), headers=h),
             client.post(f"/api/v1/policies/{p['policy_id']}/versions", json=version_body(), headers=h),
             client.patch(f"/api/v1/policies/{p['policy_id']}/activation", json={"is_active": False}, headers=h)]
    for call in calls:
        r = await call
        assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER", "OPERATOR", "VIEWER"])
async def test_every_logged_in_role_can_read_policies(client, make_user, role):
    a = await admin(client, make_user)
    p = await new_policy(client, a)
    h = await headers_for(client, make_user, "reader", role)
    assert (await client.get("/api/v1/policies", headers=h)).status_code == 200
    assert (await client.get(f"/api/v1/policies/{p['policy_id']}", headers=h)).status_code == 200


async def test_policies_need_login(client):
    assert (await client.get("/api/v1/policies")).status_code == 401
    assert (await client.post("/api/v1/policies", json=body())).status_code == 401


# ======================================= POL-01 create ============================================

async def test_create_policy_matches_the_contract_example(client, make_user, db):
    h = await admin(client, make_user)
    r = await client.post("/api/v1/policies", json=json.loads((EXAMPLES / "POL-01.request.json").read_text()), headers=h)
    assert r.status_code == 201
    policy = PolicyResponse.model_validate(r.json())
    assert policy.version == 1 and policy.is_active is True and policy.supersedes_policy_id is None
    assert set(r.json()) == set(json.loads((EXAMPLES / "POL-01.response.json").read_text()))
    event = audit_rows(db, "POLICY_CREATED")[0]
    assert str(event["entity_id"]) == r.json()["policy_id"] and event["actor_type"] == "USER"
    assert event["event_data"]["policy_key"] == policy.policy_key and event["event_data"]["version"] == 1


async def test_creator_and_conditions_are_stored(client, make_user, db):
    h = await admin(client, make_user)
    boss = db("SELECT user_id FROM users WHERE username='boss'")[0]["user_id"]
    p = await new_policy(client, h)
    assert p["created_by_user_id"] == str(boss) and p["conditions"] == BIG_PAYMENT


async def test_scope_fields_are_kept(client, make_user):
    h = await admin(client, make_user)
    agent = (await client.post("/api/v1/agents", json={"agent_name": "scoped-agent", "agent_category": "FINANCE"}, headers=h)).json()
    p = await new_policy(client, h, scope_agent_id=agent["agent_id"], scope_agent_category="FINANCE",
                         scope_action_type="FINANCE_PROPOSE_PAYMENT")
    assert (p["scope_agent_id"], p["scope_agent_category"], p["scope_action_type"]) == (
        agent["agent_id"], "FINANCE", "FINANCE_PROPOSE_PAYMENT")


async def test_duplicate_policy_key_is_409(client, make_user):
    h = await admin(client, make_user)
    await new_policy(client, h)
    r = await client.post("/api/v1/policies", json=body(), headers=h)
    assert r.status_code == 409 and r.json()["details"][0]["field"] == "policy_key"


@pytest.mark.parametrize("override", [
    {"effect": "ALLOW", "mandatory": True},                       # mandatory must be BLOCK
    {"effect": "HUMAN_REVIEW", "mandatory": True},
    {"key": "Bad_Key"}, {"key": "9starts-with-digit"}, {"key": "a"}, {"key": "has space"},
    {"priority": 0}, {"priority": 1001}, {"effect": "MAYBE"},
    {"conditions": {"all": [], "any": []}},                       # empty
    {"conditions": {"all": [{"field": "password", "operator": "EQ", "value": "x"}], "any": []}},
    {"conditions": {"all": [{"field": "payload.amount", "operator": "GT", "value": "lots"}], "any": []}},
    {"conditions": {"all": [{"field": "action_type", "operator": "EQ", "value": "MAKE_COFFEE"}], "any": []}},
    {"conditions": {"all": [{"field": "payload.x", "operator": "SOMETIMES", "value": 1}], "any": []}},
    {"scope_agent_id": UNKNOWN_ID}, {"scope_agent_category": "PIRATE"}, {"scope_action_type": "MAKE_COFFEE"},
    {"surprise": 1},
])
async def test_create_policy_validation(client, make_user, override):
    h = await admin(client, make_user)
    request = body(**{k: v for k, v in override.items() if k in ("key", "effect", "priority", "mandatory", "conditions")})
    request.update({k: v for k, v in override.items() if k not in ("key", "effect", "priority", "mandatory", "conditions")})
    r = await client.post("/api/v1/policies", json=request, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_validation_reports_every_bad_condition(client, make_user):
    h = await admin(client, make_user)
    bad = {"all": [{"field": "nope", "operator": "EQ", "value": 1}], "any": [{"field": "payload.x", "operator": "GT", "value": "a"}]}
    r = await client.post("/api/v1/policies", json=body(conditions=bad), headers=h)
    assert {d["field"] for d in r.json()["details"]} == {"conditions.all[0]", "conditions.any[0]"}


async def test_a_rejected_policy_leaves_nothing_behind(client, make_user, db):
    h = await admin(client, make_user)
    await client.post("/api/v1/policies", json=body(effect="ALLOW", mandatory=True), headers=h)
    assert db("SELECT count(*) AS n FROM policies")[0]["n"] == 0 and audit_rows(db, "POLICY_CREATED") == []


# ======================================= POL-04 new version =======================================

async def test_new_version_replaces_the_active_one(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    r = await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)
    assert r.status_code == 201
    v2 = PolicyResponse.model_validate(r.json())
    assert (v2.version, v2.policy_key, v2.is_active) == (2, "block-big-payment", True)
    assert str(v2.supersedes_policy_id) == v1["policy_id"] and (v2.effect.value, v2.priority) == ("HUMAN_REVIEW", 20)
    assert active_versions(db, "block-big-payment") == [2]
    assert (await client.get(f"/api/v1/policies/{v1['policy_id']}", headers=h)).json()["is_active"] is False
    event = audit_rows(db, "POLICY_VERSION_CREATED")[0]["event_data"]
    assert (event["version"], event["previous_version"], event["deactivated_policy_id"]) == (2, 1, v1["policy_id"])


async def test_old_version_content_is_never_changed(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(effect="ALLOW", priority=99), headers=h)
    old = (await client.get(f"/api/v1/policies/{v1['policy_id']}", headers=h)).json()
    assert (old["effect"], old["priority"], old["conditions"], old["version"]) == ("BLOCK", 10, BIG_PAYMENT, 1)


async def test_version_numbers_always_follow_the_latest_even_from_an_old_id(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    v2 = (await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)).json()
    v3 = (await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)).json()  # from v1's id
    assert (v3["version"], v3["supersedes_policy_id"]) == (3, v2["policy_id"])
    assert active_versions(db, "block-big-payment") == [3]


async def test_a_bad_new_version_keeps_the_current_one_active(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    bad = await client.post(f"/api/v1/policies/{v1['policy_id']}/versions",
                            json=version_body(effect="ALLOW", mandatory=True), headers=h)
    assert bad.status_code == 422
    assert active_versions(db, "block-big-payment") == [1]
    assert db("SELECT count(*) AS n FROM policies")[0]["n"] == 1


async def test_new_version_can_start_when_nothing_is_active(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    await client.patch(f"/api/v1/policies/{v1['policy_id']}/activation", json={"is_active": False}, headers=h)
    r = await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)
    assert r.status_code == 201 and active_versions(db, "block-big-payment") == [2]
    assert audit_rows(db, "POLICY_VERSION_CREATED")[0]["event_data"]["deactivated_policy_id"] is None


async def test_contract_example_for_a_new_version_is_accepted(client, make_user):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    example = json.loads((EXAMPLES / "POL-04.request.json").read_text())
    r = await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=example, headers=h)
    assert r.status_code == 201
    assert set(r.json()) == set(json.loads((EXAMPLES / "POL-04.response.json").read_text()))


async def test_version_of_unknown_policy_is_404_and_bad_body_is_422(client, make_user):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    assert (await client.post(f"/api/v1/policies/{UNKNOWN_ID}/versions", json=version_body(), headers=h)).status_code == 404
    for bad in ({}, {**version_body(), "policy_key": "renamed"}, {**version_body(), "priority": 0}):
        assert (await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=bad, headers=h)).status_code == 422


async def test_two_admins_creating_a_version_at_once_never_clash(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    url = f"/api/v1/policies/{v1['policy_id']}/versions"
    first, second = await asyncio.gather(client.post(url, json=version_body(priority=21), headers=h),
                                         client.post(url, json=version_body(priority=22), headers=h))
    assert {first.status_code, second.status_code} == {201}
    assert sorted(r["version"] for r in db("SELECT version FROM policies WHERE policy_key='block-big-payment'")) == [1, 2, 3]
    assert len(active_versions(db, "block-big-payment")) == 1


# ======================================= POL-05 activation ========================================

async def test_deactivate_and_audit(client, make_user, db):
    h = await admin(client, make_user)
    p = await new_policy(client, h)
    r = await client.patch(f"/api/v1/policies/{p['policy_id']}/activation", json={"is_active": False}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    event = audit_rows(db, "POLICY_ACTIVATION_CHANGED")[0]["event_data"]
    assert (event["is_active_from"], event["is_active_to"], event["version"]) == (True, False, 1)


async def test_cannot_activate_a_second_version_while_another_is_active(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)  # v2 active
    r = await client.patch(f"/api/v1/policies/{v1['policy_id']}/activation", json={"is_active": True}, headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "INVALID_STATE_TRANSITION"
    assert active_versions(db, "block-big-payment") == [2]


async def test_roll_back_by_deactivating_the_new_version_then_activating_the_old(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    v2 = (await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)).json()
    assert (await client.patch(f"/api/v1/policies/{v2['policy_id']}/activation", json={"is_active": False}, headers=h)).status_code == 200
    assert (await client.patch(f"/api/v1/policies/{v1['policy_id']}/activation", json={"is_active": True}, headers=h)).status_code == 200
    assert active_versions(db, "block-big-payment") == [1]


async def test_setting_the_same_state_changes_and_logs_nothing(client, make_user, db):
    h = await admin(client, make_user)
    p = await new_policy(client, h)
    r = await client.patch(f"/api/v1/policies/{p['policy_id']}/activation", json={"is_active": True}, headers=h)
    assert r.status_code == 200 and audit_rows(db, "POLICY_ACTIVATION_CHANGED") == []


async def test_activation_validation_and_404(client, make_user):
    h = await admin(client, make_user)
    p = await new_policy(client, h)
    url = f"/api/v1/policies/{p['policy_id']}/activation"
    for bad in ({}, {"is_active": "maybe"}, {"is_active": True, "extra": 1}):
        assert (await client.patch(url, json=bad, headers=h)).status_code == 422
    assert (await client.patch(f"/api/v1/policies/{UNKNOWN_ID}/activation", json={"is_active": True}, headers=h)).status_code == 404


async def test_the_database_itself_refuses_two_active_versions(client, make_user, db):
    h = await admin(client, make_user)
    await new_policy(client, h)
    with pytest.raises(IntegrityError):
        db("INSERT INTO policies (policy_key,version,name,effect,priority,conditions,is_active) "
           "VALUES ('block-big-payment',2,'x','BLOCK',5,'{}',true)")


# ======================================= POL-02 / POL-03 read =====================================

async def test_list_filters_paging_and_sorting(client, make_user):
    h = await admin(client, make_user)
    await new_policy(client, h, key="alpha-block", priority=30)
    beta = await new_policy(client, h, key="beta-review", effect="HUMAN_REVIEW", priority=20)
    await new_policy(client, h, key="gamma-allow", effect="ALLOW", priority=10)
    await client.patch(f"/api/v1/policies/{beta['policy_id']}/activation", json={"is_active": False}, headers=h)

    page = PolicyResponsePage.model_validate((await client.get(
        "/api/v1/policies", params={"sort_by": "priority", "sort_order": "asc", "page_size": 2}, headers=h)).json())
    assert [p.policy_key for p in page.items] == ["gamma-allow", "beta-review"] and (page.total_items, page.total_pages) == (3, 2)
    assert (await client.get("/api/v1/policies", params={"effect": "BLOCK"}, headers=h)).json()["total_items"] == 1
    off = (await client.get("/api/v1/policies", params={"is_active": "false"}, headers=h)).json()
    assert [p["policy_key"] for p in off["items"]] == ["beta-review"]
    assert (await client.get("/api/v1/policies", params={"policy_key": "gamma-allow"}, headers=h)).json()["total_items"] == 1


async def test_list_shows_every_version_of_a_policy(client, make_user):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    await client.post(f"/api/v1/policies/{v1['policy_id']}/versions", json=version_body(), headers=h)
    items = (await client.get("/api/v1/policies", params={"policy_key": "block-big-payment", "sort_by": "policy_key"}, headers=h)).json()["items"]
    assert sorted(i["version"] for i in items) == [1, 2]


@pytest.mark.parametrize("params", [{"sort_by": "conditions"}, {"page_size": 101}, {"page": 0}, {"effect": "MAYBE"}])
async def test_list_rejects_bad_query(client, make_user, params):
    h = await admin(client, make_user)
    assert (await client.get("/api/v1/policies", params=params, headers=h)).status_code == 422


async def test_get_policy_and_404(client, make_user):
    h = await admin(client, make_user)
    p = await new_policy(client, h)
    assert PolicyResponse.model_validate((await client.get(f"/api/v1/policies/{p['policy_id']}", headers=h)).json()).policy_key == "block-big-payment"
    assert (await client.get(f"/api/v1/policies/{UNKNOWN_ID}", headers=h)).status_code == 404
    assert (await client.get("/api/v1/policies/not-a-uuid", headers=h)).status_code == 422


# ============================ the service re-checks ADMIN itself ====================================

@pytest.fixture
async def session():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    async with async_sessionmaker(eng, expire_on_commit=False)() as s:
        yield s
    await eng.dispose()


@pytest.mark.parametrize("role", ["REVIEWER", "OPERATOR", "VIEWER"])
async def test_policy_service_refuses_non_admins_directly(session, role):
    from app.core.enums import UserRole
    from app.core.exceptions import AppError
    from app.schemas import (ActorContext, PolicyActivationRequest, PolicyCreateRequest, PolicyVersionCreateRequest)
    from app.services import policy_service

    actor = ActorContext(user_id=uuid.uuid4(), username="x", role=UserRole(role))
    calls = [
        policy_service.create_policy(session, PolicyCreateRequest.model_validate(body()), actor),
        policy_service.create_policy_version(session, uuid.uuid4(), PolicyVersionCreateRequest.model_validate(version_body()), actor),
        policy_service.set_policy_activation(session, uuid.uuid4(), PolicyActivationRequest(is_active=False), actor),
    ]
    for call in calls:
        with pytest.raises(AppError) as e:
            await call
        assert e.value.error_code.value == "AUTH_INSUFFICIENT_ROLE"


async def test_many_concurrent_new_versions_all_succeed_with_unique_numbers(client, make_user, db):
    h = await admin(client, make_user)
    v1 = await new_policy(client, h)
    url = f"/api/v1/policies/{v1['policy_id']}/versions"
    results = await asyncio.gather(*[client.post(url, json=version_body(priority=20 + i), headers=h) for i in range(6)])
    assert [r.status_code for r in results] == [201] * 6
    assert sorted(r["version"] for r in db("SELECT version FROM policies WHERE policy_key='block-big-payment'")) == [1, 2, 3, 4, 5, 6, 7]
    assert len(active_versions(db, "block-big-payment")) == 1
    chain = db("SELECT version, supersedes_policy_id, policy_id FROM policies WHERE policy_key='block-big-payment' ORDER BY version")
    for earlier, later in zip(chain, chain[1:]):  # every version supersedes the one right before it
        assert later["supersedes_policy_id"] == earlier["policy_id"]
