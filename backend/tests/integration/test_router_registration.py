"""Student 2's routers are mounted under /api/v1, and the ones that do not check the login themselves are protected."""

import uuid

import pytest

from tests.integration.api_support import client, db, env, headers_for, make_user  # noqa: F401
from tests.integration.conftest import TEST_URL

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")]

ID = uuid.uuid4()
ROUTES = [
    ("GET", f"/api/v1/agents/{ID}/scenarios"),
    ("POST", f"/api/v1/agents/{ID}/runs"),
    ("POST", "/api/v1/risk-assessments/dry-run"),
    ("GET", "/api/v1/risk-assessments"),
    ("GET", f"/api/v1/risk-assessments/{ID}"),
    ("POST", "/api/v1/evaluations/runs"),
    ("GET", "/api/v1/evaluations"),
    ("GET", "/api/v1/evaluations/overview"),
    ("GET", "/api/v1/evaluations/agent-performance"),
    ("GET", f"/api/v1/evaluations/{ID}"),
]


@pytest.mark.parametrize("method,path", ROUTES)
async def test_every_route_needs_a_login(client, method, path):
    r = await client.request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 401, (method, path, r.status_code)
    assert r.json()["error_code"] == "AUTH_MISSING_CREDENTIALS"


@pytest.mark.parametrize("method,path", ROUTES)
async def test_a_logged_in_user_reaches_the_route(client, make_user, method, path):
    h = await headers_for(client, make_user, "reach-admin", "ADMIN")
    r = await client.request(method, path, json={} if method == "POST" else None, headers=h)
    assert r.status_code != 404 or r.json().get("error_code") == "RESOURCE_NOT_FOUND", (method, path, r.text)
    assert r.status_code != 401
