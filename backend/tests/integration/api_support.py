"""Shared fixtures for API integration tests (import the fixtures you need into a test module)."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.main import create_app
from tests.integration.conftest import TEST_URL

PASSWORD = "Correct-Horse-12"


@pytest.fixture(autouse=True)
def env(monkeypatch, engine):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", TEST_URL or "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)
    get_settings.cache_clear()
    with engine.begin() as c:  # audit_events is append-only; TRUNCATE is how tests reset it
        c.execute(text("TRUNCATE users, tools, policies, audit_events RESTART IDENTITY CASCADE"))
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client():
    app = create_app()
    async_engine = create_async_engine(TEST_URL, poolclass=NullPool)
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await async_engine.dispose()


@pytest.fixture
def db(engine):
    def run(sql, **params):
        with engine.begin() as c:
            result = c.execute(text(sql), params)
            return list(result.mappings()) if result.returns_rows else None

    return run


@pytest.fixture
def make_user(db):
    def make(username, role="VIEWER", active=True, password=PASSWORD):
        rows = db(
            "INSERT INTO users (username,email,password_hash,role,is_active) VALUES (:u,:e,:h,:r,:a) RETURNING user_id",
            u=username, e=f"{username}@x.test", h=security.hash_password(password), r=role, a=active,
        )
        return rows[0]["user_id"]

    return make


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def token_of(client, username, password=PASSWORD):
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def headers_for(client, make_user, name, role):
    make_user(name, role)
    return auth(await token_of(client, name))


def audit_rows(db, event_name):
    return db("SELECT * FROM audit_events WHERE event_name=:n ORDER BY created_at", n=event_name)
