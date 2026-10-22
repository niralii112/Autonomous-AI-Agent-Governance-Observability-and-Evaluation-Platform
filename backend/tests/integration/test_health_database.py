import httpx
import pytest

from app.core import database
from app.core.config import get_settings
from app.main import create_app
from app.schemas import HealthResponse
from tests.integration.conftest import TEST_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture(autouse=True)
def env(monkeypatch, engine):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    for fn in (get_settings, database.get_engine, database.get_session_factory):
        fn.cache_clear()
    yield
    for fn in (get_settings, database.get_engine, database.get_session_factory):
        fn.cache_clear()


async def test_health_with_a_real_database_is_ok():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/system/health")
    body = HealthResponse.model_validate(r.json())
    assert r.status_code == 200 and body.status.value == "OK"


async def test_health_reports_down_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://governance_user:pw@127.0.0.1:1/nope")
    for fn in (get_settings, database.get_engine, database.get_session_factory):
        fn.cache_clear()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/system/health")
    assert r.status_code == 200 and r.json()["status"] == "DOWN"
