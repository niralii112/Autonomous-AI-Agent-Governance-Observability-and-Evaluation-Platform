import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
CONTRACT_FILE = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "policies" / "seed-policies.json"
spec = importlib.util.spec_from_file_location("seed_script_policies", SEED_PATH)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

IT_KEYS = {"block-production-privileged-config", "review-production-restart", "allow-staging-restart"}


@pytest.fixture(autouse=True)
def clean(engine):
    with engine.begin() as c:
        c.execute(text("TRUNCATE users, tools, policies, audit_events RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session_factory():
    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


async def run(factory):
    async with factory() as s:
        result = await seed.seed_policies(s)
        await s.commit()
    return result


def q(engine, sql):
    with engine.connect() as c:
        return list(c.execute(text(sql)).mappings())


def contract_policies():
    data = json.loads(CONTRACT_FILE.read_text())
    items = data["policies"] if isinstance(data, dict) else data
    return [p for p in items if p["policy_key"] not in IT_KEYS]


def test_embedded_seed_list_equals_the_contract_file_without_it_policies():
    assert len(contract_policies()) == 10
    assert seed.SEED_POLICIES == contract_policies()


async def test_creates_the_10_policies_as_active_version_1(session_factory, engine):
    result = await run(session_factory)
    assert list(result.values()).count("created") == 10
    rows = q(engine, "SELECT * FROM policies")
    assert len(rows) == 10 and all(r["version"] == 1 and r["is_active"] for r in rows)
    assert all(r["supersedes_policy_id"] is None and r["name"] for r in rows)


async def test_stored_rows_match_the_contract(session_factory, engine):
    await run(session_factory)
    stored = {r["policy_key"]: r for r in q(engine, "SELECT * FROM policies")}
    for item in contract_policies():
        row = stored[item["policy_key"]]
        assert (row["effect"], row["priority"], row["is_mandatory"]) == (item["effect"], item["priority"], item["is_mandatory"])
        assert row["conditions"] == item["conditions"]


async def test_no_it_operations_policy_is_seeded(session_factory, engine):
    await run(session_factory)
    assert not (IT_KEYS & {r["policy_key"] for r in q(engine, "SELECT policy_key FROM policies")})


async def test_every_mandatory_policy_is_a_block(session_factory, engine):
    await run(session_factory)
    mandatory = q(engine, "SELECT effect FROM policies WHERE is_mandatory")
    assert mandatory and {r["effect"] for r in mandatory} == {"BLOCK"}


async def test_effect_counts_are_3_block_4_review_3_allow(session_factory, engine):
    await run(session_factory)
    counts = {r["effect"]: r["n"] for r in q(engine, "SELECT effect, count(*) AS n FROM policies GROUP BY effect")}
    assert counts == {"BLOCK": 3, "HUMAN_REVIEW": 4, "ALLOW": 3}


async def test_running_twice_creates_nothing_new(session_factory, engine):
    await run(session_factory)
    again = await run(session_factory)
    assert set(again.values()) == {"exists"}
    assert q(engine, "SELECT count(*) AS n FROM policies")[0]["n"] == 10
    assert q(engine, "SELECT count(*) AS n FROM audit_events")[0]["n"] == 10


async def test_a_policy_an_admin_has_versioned_is_not_touched(session_factory, engine):
    await run(session_factory)
    with engine.begin() as c:  # pretend an admin made version 2 and retired version 1
        c.execute(text("UPDATE policies SET is_active=false WHERE policy_key='block-large-payment'"))
        c.execute(text("INSERT INTO policies (policy_key,version,name,effect,priority,conditions,is_active) "
                       "SELECT policy_key,2,name,effect,priority,conditions,true FROM policies WHERE policy_key='block-large-payment'"))
    await run(session_factory)
    rows = q(engine, "SELECT version, is_active FROM policies WHERE policy_key='block-large-payment' ORDER BY version")
    assert [(r["version"], r["is_active"]) for r in rows] == [(1, False), (2, True)]


async def test_seeding_is_audited_as_system(session_factory, engine):
    await run(session_factory)
    rows = q(engine, "SELECT event_name, actor_type, actor_user_id, event_data FROM audit_events")
    assert len(rows) == 10 and {r["event_name"] for r in rows} == {"POLICY_CREATED"}
    assert all(r["actor_type"] == "SYSTEM" and r["actor_user_id"] is None and r["event_data"]["source"] == "seed" for r in rows)
