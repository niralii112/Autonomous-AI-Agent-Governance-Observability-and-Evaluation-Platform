"""SYS-02 GET /api/v1/system/info: build and configuration facts, for any logged-in role."""

import json
from pathlib import Path

import pytest

from app.schemas import SystemInfoResponse
from tests.integration.api_support import client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

EXAMPLE = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "SYS-02.response.json"


async def test_system_info_needs_login(client):
    assert (await client.get("/api/v1/system/info")).status_code == 401


@pytest.mark.parametrize("role", ["ADMIN", "REVIEWER", "OPERATOR", "VIEWER"])
async def test_every_role_can_read_system_info(client, make_user, role):
    h = await headers_for(client, make_user, f"info-{role.lower()}", role)
    r = await client.get("/api/v1/system/info", headers=h)
    assert r.status_code == 200, r.text
    body = SystemInfoResponse.model_validate(r.json())
    assert (body.app_version, body.api_version, body.contract_version) == ("1.0.0", "v1", "1.0.0")
    assert set(r.json()) == set(json.loads(EXAMPLE.read_text()))


async def test_without_any_model_row_the_heuristic_is_reported(client, make_user):
    h = await headers_for(client, make_user, "info-admin", "ADMIN")
    body = (await client.get("/api/v1/system/info", headers=h)).json()
    assert body["active_model_version"] is None and body["active_risk_source"] == "HEURISTIC_FALLBACK"


async def test_the_active_model_is_reported(client, make_user, db):
    db("INSERT INTO model_versions (model_version, model_kind, algorithm, feature_schema_version, is_active) "
       "VALUES ('heuristic-v1','HEURISTIC_FALLBACK','rules','1', true)")
    h = await headers_for(client, make_user, "info-admin", "ADMIN")
    body = (await client.get("/api/v1/system/info", headers=h)).json()
    assert (body["active_model_version"], body["active_risk_source"]) == ("heuristic-v1", "HEURISTIC_FALLBACK")
    db("INSERT INTO model_versions (model_version, model_kind, algorithm, feature_schema_version, is_active) "
       "VALUES ('risk-logreg-1.0.0','ML_MODEL','logreg','1', true)")
    body = (await client.get("/api/v1/system/info", headers=h)).json()
    assert (body["active_model_version"], body["active_risk_source"]) == ("risk-logreg-1.0.0", "ML_MODEL")
