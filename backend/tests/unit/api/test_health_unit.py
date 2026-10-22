import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.database import get_session
from app.core.enums import HealthStatus
from app.main import create_app
from app.schemas import HealthResponse


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class WorkingSession:
    async def execute(self, *_):
        return None


class BrokenSession:
    async def execute(self, *_):
        raise OperationalError("SELECT 1", {}, Exception("connection refused host=10.1.2.3"))


def client_with(session):
    app = create_app()

    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_health_ok():
    async with client_with(WorkingSession()) as c:
        r = await c.get("/api/v1/system/health")
    assert r.status_code == 200
    body = HealthResponse.model_validate(r.json())
    assert body.status == HealthStatus.OK and body.version == "1.0.0"
    assert body.components[0].component_name == "database"
    assert body.components[0].status == HealthStatus.OK and body.components[0].latency_ms is not None


async def test_health_down_is_still_200_and_leaks_nothing():
    async with client_with(BrokenSession()) as c:
        r = await c.get("/api/v1/system/health")
    assert r.status_code == 200
    body = HealthResponse.model_validate(r.json())
    assert body.status == HealthStatus.DOWN
    assert body.components[0].status == HealthStatus.DOWN
    assert "10.1.2.3" not in r.text and "refused" not in r.text


async def test_health_needs_no_login():
    async with client_with(WorkingSession()) as c:
        assert (await c.get("/api/v1/system/health")).status_code == 200


async def test_openapi_is_served_and_lists_health():
    async with client_with(WorkingSession()) as c:
        r = await c.get("/api/v1/openapi.json")
    assert r.status_code == 200 and "/api/v1/system/health" in r.json()["paths"]


async def test_cors_allows_only_configured_origin():
    async with client_with(WorkingSession()) as c:
        ok = await c.get("/api/v1/system/health", headers={"Origin": "http://localhost:5173"})
        bad = await c.get("/api/v1/system/health", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_importing_main_needs_no_settings_but_app_attribute_builds_it():
    import app.main as main
    assert main.app.title == "Agent Governance Platform"
