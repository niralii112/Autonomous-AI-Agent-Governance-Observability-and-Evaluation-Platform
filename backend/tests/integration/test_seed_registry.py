import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
spec = importlib.util.spec_from_file_location("seed_script_registry", SEED_PATH)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

FINANCE = {"finance_report_reader", "finance_summary_generator", "payment_processor_sim", "finance_records_vault"}
SUPPORT = {"ticket_reader", "support_response_generator", "refund_processor_sim", "customer_info_accessor"}


@pytest.fixture(autouse=True)
def clean(engine):
    with engine.begin() as c:
        c.execute(text("TRUNCATE users, tools, audit_events RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session_factory():
    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


async def run(factory):
    async with factory() as s:
        result = await seed.seed_registry(s)
        await s.commit()
    return result


def q(engine, sql):
    with engine.connect() as c:
        return list(c.execute(text(sql)).mappings())


async def test_creates_8_tools_and_2_agents(session_factory, engine):
    result = await run(session_factory)
    assert sum(v == "created" for v in result.values()) == 10
    tools = {r["tool_name"]: r for r in q(engine, "SELECT * FROM tools")}
    assert set(tools) == FINANCE | SUPPORT
    agents = {r["agent_name"]: r for r in q(engine, "SELECT * FROM agents")}
    assert set(agents) == {"finance-agent-01", "support-agent-01"}
    assert agents["finance-agent-01"]["agent_category"] == "FINANCE"
    assert agents["support-agent-01"]["agent_category"] == "CUSTOMER_SUPPORT"
    assert all(a["trust_tier"] == 2 and a["agent_status"] == "ACTIVE" for a in agents.values())


async def test_no_it_operations_anything_is_seeded(session_factory, engine):
    await run(session_factory)
    assert not q(engine, "SELECT 1 FROM tools WHERE supported_action_type LIKE 'IT\\_%'")
    assert not q(engine, "SELECT 1 FROM agents WHERE agent_category = 'IT_OPERATIONS'")


async def test_tool_sensitivities_and_action_types_match_the_spec(session_factory, engine):
    await run(session_factory)
    got = {r["tool_name"]: (r["tool_sensitivity"], r["supported_action_type"]) for r in q(engine, "SELECT * FROM tools")}
    assert got["payment_processor_sim"] == ("WRITE", "FINANCE_PROPOSE_PAYMENT")
    assert got["refund_processor_sim"] == ("WRITE", "SUPPORT_PROPOSE_REFUND")
    assert got["finance_records_vault"] == ("SENSITIVE_READ", "FINANCE_ACCESS_SENSITIVE_RECORDS")
    assert got["customer_info_accessor"] == ("SENSITIVE_READ", "SUPPORT_ACCESS_CUSTOMER_INFO")
    assert got["ticket_reader"] == ("READ_ONLY", "SUPPORT_GET_TICKET")
    assert len({v[1] for v in got.values()}) == 8  # one tool per action type


async def test_permission_matrix_is_16_rows_with_own_tools_allowed(session_factory, engine):
    await run(session_factory)
    rows = q(engine, "SELECT a.agent_name, t.tool_name, p.is_allowed FROM agent_tool_permissions p "
                     "JOIN agents a USING (agent_id) JOIN tools t USING (tool_id)")
    assert len(rows) == 16
    allowed = {}
    for r in rows:
        allowed.setdefault(r["agent_name"], set())
        if r["is_allowed"]:
            allowed[r["agent_name"]].add(r["tool_name"])
    assert allowed == {"finance-agent-01": FINANCE, "support-agent-01": SUPPORT}


async def test_running_twice_changes_nothing(session_factory, engine):
    await run(session_factory)
    again = await run(session_factory)
    assert set(again.values()) == {"exists"}
    assert q(engine, "SELECT count(*) AS n FROM agent_tool_permissions")[0]["n"] == 16
    assert q(engine, "SELECT count(*) AS n FROM audit_events")[0]["n"] == 8 + 2 * 2


async def test_an_admins_permission_change_survives_reseeding(session_factory, engine):
    await run(session_factory)
    with engine.begin() as c:
        c.execute(text("DELETE FROM agent_tool_permissions WHERE agent_id = "
                       "(SELECT agent_id FROM agents WHERE agent_name='finance-agent-01')"))
    await run(session_factory)
    n = q(engine, "SELECT count(*) AS n FROM agent_tool_permissions p JOIN agents a USING (agent_id) "
                  "WHERE a.agent_name='finance-agent-01'")[0]["n"]
    assert n == 0  # not silently restored


async def test_seeding_is_audited_as_system(session_factory, engine):
    await run(session_factory)
    rows = q(engine, "SELECT event_name, actor_type, event_data FROM audit_events")
    assert {r["actor_type"] for r in rows} == {"SYSTEM"}
    names = [r["event_name"] for r in rows]
    assert names.count("TOOL_REGISTERED") == 8 and names.count("AGENT_REGISTERED") == 2 and names.count("AGENT_UPDATED") == 2
    grant = next(r for r in rows if r["event_name"] == "AGENT_UPDATED")["event_data"]
    assert len(grant["granted"]) == 4 and len(grant["denied"]) == 4
