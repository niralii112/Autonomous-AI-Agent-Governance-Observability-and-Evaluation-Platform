import json
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import agent_runs
from app.core.config import get_settings
from app.core.database import get_session
from app.core.enums import ErrorCode, UserRole
from app.core.error_handlers import register_error_handlers
from app.core.exceptions import NotFoundError
from app.dependencies.auth import get_current_actor
from app.schemas import ActorContext, AgentRunResponse, AgentScenarioListResponse

EXAMPLES = Path(__file__).resolve().parents[4] / "contracts" / "examples"
SCENARIOS_EXAMPLE = AgentScenarioListResponse.model_validate(
    json.loads((EXAMPLES / "AGT-07.response.json").read_text())
)
RUN_EXAMPLE = AgentRunResponse.model_validate(
    json.loads((EXAMPLES / "AGT-08.response.json").read_text())
)
AGENT_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def api(monkeypatch):
    """A small app with only our router. `role` decides who is calling."""
    state = {"role": UserRole.OPERATOR, "calls": []}

    async def fake_actor():
        return ActorContext(user_id=uuid.uuid4(), username="tester", role=state["role"])

    async def fake_session():
        yield object()

    async def fake_list(session, agent_id):
        return SCENARIOS_EXAMPLE

    async def fake_run(session, agent_id, request, actor):
        state["calls"].append(request)
        return RUN_EXAMPLE

    monkeypatch.setattr(agent_runs.agent_run_service, "list_agent_scenarios", fake_list)
    monkeypatch.setattr(agent_runs.agent_run_service, "run_agent_scenario", fake_run)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(agent_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_current_actor] = fake_actor
    app.dependency_overrides[get_session] = fake_session

    return TestClient(app), state


def test_anyone_logged_in_can_list_scenarios(api):
    client, state = api
    state["role"] = UserRole.VIEWER

    response = client.get(f"/api/v1/agents/{AGENT_ID}/scenarios")

    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == len(SCENARIOS_EXAMPLE.scenarios)


def test_operator_can_run_a_scenario(api):
    client, state = api

    response = client.post(
        f"/api/v1/agents/{AGENT_ID}/runs",
        json={"scenario_key": "finance.payment.small"},
    )

    assert response.status_code == 200
    assert response.json()["scenario_key"] == RUN_EXAMPLE.scenario_key
    assert state["calls"][0].scenario_key == "finance.payment.small"


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.REVIEWER])
def test_other_roles_cannot_run_a_scenario(api, role):
    client, state = api
    state["role"] = role

    response = client.post(
        f"/api/v1/agents/{AGENT_ID}/runs",
        json={"scenario_key": "finance.payment.small"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == ErrorCode.AUTH_INSUFFICIENT_ROLE.value
    assert state["calls"] == []


def test_run_without_a_scenario_key_is_rejected(api):
    client, state = api

    response = client.post(f"/api/v1/agents/{AGENT_ID}/runs", json={})

    assert response.status_code == 422
    assert state["calls"] == []


def test_agent_id_must_be_a_uuid(api):
    client, _state = api

    assert client.get("/api/v1/agents/not-a-uuid/scenarios").status_code == 422


def test_unknown_scenario_gives_404(api, monkeypatch):
    client, _state = api

    async def missing(session, agent_id, request, actor):
        raise NotFoundError("Scenario not found.")

    monkeypatch.setattr(agent_runs.agent_run_service, "run_agent_scenario", missing)

    response = client.post(
        f"/api/v1/agents/{AGENT_ID}/runs", json={"scenario_key": "finance.nope"}
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == ErrorCode.RESOURCE_NOT_FOUND.value
