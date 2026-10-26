"""DEC-01 and DEC-02 against a real database. Decisions are inserted directly, because
submit_action (which creates them) does not exist yet."""

import json
import uuid
from pathlib import Path

import pytest

from app.schemas import GovernanceDecisionResponse, GovernanceDecisionResponsePage
from tests.integration.api_support import (  # noqa: F401  (fixtures are used by name)
    client, db, env, headers_for, make_user,
)
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
HASH = "a" * 64


@pytest.fixture
def agent_id(db):
    return db("INSERT INTO agents (agent_name,agent_category) VALUES ('dec-agent','FINANCE') RETURNING agent_id")[0]["agent_id"]


def new_action(db, agent_id):
    return db("INSERT INTO actions (agent_id,requested_tool_name,action_type,action_payload,payload_hash,idempotency_key) "
              "VALUES (:a,'t','FINANCE_PROPOSE_PAYMENT','{}',:h,:k) RETURNING action_id",
              a=agent_id, h=HASH, k=uuid.uuid4().hex)[0]["action_id"]


def new_decision(db, action_id, *, seq=1, policy="ALLOW", final="ALLOW", rule="D-13", reason="POLICY_ALLOW_LOW_RISK",
                 created_at="2026-10-20T10:00:00+00:00", matched=None):
    return db("INSERT INTO governance_decisions (action_id,decision_sequence,policy_result,final_decision,decision_reason_code,"
              "decision_rule_id,matched_policy_ids,policy_snapshot_hash,payload_hash,created_at) "
              "VALUES (:a,:s,:p,:f,:c,:r,CAST(:m AS jsonb),:h,:h,:t) RETURNING governance_decision_id",
              a=action_id, s=seq, p=policy, f=final, c=reason, r=rule, m=json.dumps(matched or []), h=HASH, t=created_at)[0]["governance_decision_id"]


async def anyone(client, make_user, role="VIEWER"):
    return await headers_for(client, make_user, "someone", role)


# ============================== access ===========================================================

@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER", "OPERATOR", "VIEWER"])
async def test_every_logged_in_role_can_read_decisions(client, make_user, db, agent_id, role):
    d = new_decision(db, new_action(db, agent_id))
    h = await anyone(client, make_user, role)
    assert (await client.get("/api/v1/governance-decisions", headers=h)).status_code == 200
    assert (await client.get(f"/api/v1/governance-decisions/{d}", headers=h)).status_code == 200


async def test_decisions_need_login(client):
    assert (await client.get("/api/v1/governance-decisions")).status_code == 401
    assert (await client.get(f"/api/v1/governance-decisions/{UNKNOWN_ID}")).status_code == 401


def test_there_is_no_way_to_write_decisions_through_the_api():
    from app.main import create_app
    methods = {m for r in create_app().routes if r.path.startswith("/api/v1/governance-decisions") for m in r.methods}
    assert methods <= {"GET", "HEAD"}


# ============================== DEC-02 get one ====================================================

async def test_get_decision_matches_the_contract(client, make_user, db, agent_id):
    action = new_action(db, agent_id)
    pid = str(uuid.uuid4())
    d = new_decision(db, action, final="BLOCK", policy="BLOCK", rule="D-06", reason="POLICY_BLOCK", matched=[pid])
    h = await anyone(client, make_user)
    r = await client.get(f"/api/v1/governance-decisions/{d}", headers=h)
    assert r.status_code == 200
    body = GovernanceDecisionResponse.model_validate(r.json())
    assert (body.final_decision.value, body.decision_rule_id, body.decision_reason_code) == ("BLOCK", "D-06", "POLICY_BLOCK")
    assert r.json()["matched_policy_ids"] == [pid] and r.json()["action_id"] == str(action)
    assert set(r.json()) == set(json.loads((EXAMPLES / "DEC-02.response.json").read_text()))


async def test_unknown_or_malformed_decision_id(client, make_user):
    h = await anyone(client, make_user)
    assert (await client.get(f"/api/v1/governance-decisions/{UNKNOWN_ID}", headers=h)).status_code == 404
    r = await client.get("/api/v1/governance-decisions/not-a-uuid", headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


# ============================== DEC-01 list =======================================================

async def test_list_is_newest_first_by_default_and_oldest_first_on_request(client, make_user, db, agent_id):
    a1, a2, a3 = (new_action(db, agent_id) for _ in range(3))
    old = new_decision(db, a1, created_at="2026-10-01T00:00:00+00:00")
    mid = new_decision(db, a2, created_at="2026-10-10T00:00:00+00:00")
    new = new_decision(db, a3, created_at="2026-10-20T00:00:00+00:00")
    h = await anyone(client, make_user)
    desc_ids = [i["governance_decision_id"] for i in (await client.get("/api/v1/governance-decisions", headers=h)).json()["items"]]
    asc_ids = [i["governance_decision_id"] for i in (await client.get(
        "/api/v1/governance-decisions", params={"sort_order": "asc"}, headers=h)).json()["items"]]
    assert desc_ids == [str(new), str(mid), str(old)] and asc_ids == [str(old), str(mid), str(new)]


async def test_paging(client, make_user, db, agent_id):
    for day in range(1, 6):
        new_decision(db, new_action(db, agent_id), created_at=f"2026-10-{day:02d}T00:00:00+00:00")
    h = await anyone(client, make_user)
    page2 = GovernanceDecisionResponsePage.model_validate((await client.get(
        "/api/v1/governance-decisions", params={"page": 2, "page_size": 2}, headers=h)).json())
    assert (page2.page, page2.page_size, page2.total_items, page2.total_pages, len(page2.items)) == (2, 2, 5, 3, 2)
    last = (await client.get("/api/v1/governance-decisions", params={"page": 3, "page_size": 2}, headers=h)).json()
    assert len(last["items"]) == 1


async def test_filters(client, make_user, db, agent_id):
    a_block, a_allow = new_action(db, agent_id), new_action(db, agent_id)
    new_decision(db, a_block, policy="BLOCK", final="BLOCK", rule="D-06", reason="POLICY_BLOCK")
    new_decision(db, a_allow)
    new_decision(db, a_allow, seq=2, policy="NO_MATCH", final="HUMAN_REVIEW", rule="D-09", reason="NO_POLICY_MATCH_REVIEW")
    h = await anyone(client, make_user)

    def total(**params):
        return client.get("/api/v1/governance-decisions", params=params, headers=h)

    assert (await total()).json()["total_items"] == 3
    assert (await total(final_decision="BLOCK")).json()["total_items"] == 1
    assert (await total(policy_result="NO_MATCH")).json()["total_items"] == 1
    assert (await total(action_id=str(a_allow))).json()["total_items"] == 2
    assert (await total(action_id=str(a_allow), final_decision="ALLOW")).json()["total_items"] == 1
    assert (await total(action_id=UNKNOWN_ID)).json()["total_items"] == 0


async def test_date_filters_include_the_boundaries(client, make_user, db, agent_id):
    for ts in ("2026-10-01T00:00:00+00:00", "2026-10-10T12:00:00+00:00", "2026-10-20T00:00:00+00:00"):
        new_decision(db, new_action(db, agent_id), created_at=ts)
    h = await anyone(client, make_user)

    async def total(**params):
        return (await client.get("/api/v1/governance-decisions", params=params, headers=h)).json()["total_items"]

    assert await total(created_from="2026-10-10T12:00:00Z") == 2
    assert await total(created_to="2026-10-10T12:00:00Z") == 2
    assert await total(created_from="2026-10-05T00:00:00Z", created_to="2026-10-15T00:00:00Z") == 1
    assert await total(created_from="2026-12-01T00:00:00Z") == 0


async def test_an_empty_list_has_zero_pages(client, make_user):
    h = await anyone(client, make_user)
    body = (await client.get("/api/v1/governance-decisions", headers=h)).json()
    assert body["items"] == [] and body["total_items"] == 0 and body["total_pages"] == 0


@pytest.mark.parametrize("params", [{"sort_by": "final_decision"}, {"page_size": 101}, {"page": 0}, {"action_id": "nope"},
                                    {"final_decision": "MAYBE"}, {"policy_result": "X"}, {"created_from": "yesterday"}, {"sort_order": "up"}])
async def test_bad_query_is_422(client, make_user, params):
    h = await anyone(client, make_user)
    r = await client.get("/api/v1/governance-decisions", params=params, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_list_items_follow_the_contract_shape(client, make_user, db, agent_id):
    new_decision(db, new_action(db, agent_id))
    h = await anyone(client, make_user)
    item = (await client.get("/api/v1/governance-decisions", headers=h)).json()["items"][0]
    assert set(item) == set(json.loads((EXAMPLES / "DEC-02.response.json").read_text()))
