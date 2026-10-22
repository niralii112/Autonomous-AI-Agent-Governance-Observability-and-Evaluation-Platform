import time
import uuid

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.core.enums import UserRole
from app.core.error_handlers import register_error_handlers
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import ActorContext
from tests.integration.conftest import TEST_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", TEST_URL or "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def make_user(engine):
    created = []

    def _make(role="ADMIN", active=True):
        uid = uuid.uuid4()
        name = f"u{uid.hex[:10]}"
        with engine.begin() as c:
            c.execute(text("INSERT INTO users (user_id,username,email,password_hash,role,is_active) "
                           "VALUES (:i,:n,:e,'x',:r,:a)"),
                      {"i": uid, "n": name, "e": f"{name}@x.test", "r": role, "a": active})
        created.append(uid)
        return uid, name

    yield _make
    with engine.begin() as c:
        for uid in created:
            c.execute(text("DELETE FROM users WHERE user_id=:i"), {"i": uid})


@pytest.fixture
async def client(engine):
    app = FastAPI()
    register_error_handlers(app)
    async_engine = create_async_engine(TEST_URL, poolclass=NullPool)
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    @app.get("/me")
    async def me(actor: ActorContext = Depends(get_current_actor)):
        return actor

    @app.get("/admin-only")
    async def admin_only(actor: ActorContext = Depends(require_roles(UserRole.ADMIN))):
        return {"who": actor.username}

    @app.get("/staff")
    async def staff(actor: ActorContext = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))):
        return {"who": actor.username}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await async_engine.dispose()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def token_for(uid, name, role="ADMIN"):
    return security.create_access_token(uid, name, UserRole(role))


async def test_valid_token_returns_the_actor(client, make_user):
    uid, name = make_user("REVIEWER")
    r = await client.get("/me", headers=bearer(token_for(uid, name, "REVIEWER")))
    assert r.status_code == 200
    assert r.json() == {"user_id": str(uid), "username": name, "role": "REVIEWER"}


async def test_no_header_is_missing_credentials(client):
    r = await client.get("/me")
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_MISSING_CREDENTIALS"


async def test_wrong_scheme_is_missing_credentials(client):
    r = await client.get("/me", headers={"Authorization": "Basic abc123"})
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_MISSING_CREDENTIALS"


async def test_garbage_token_is_invalid(client):
    r = await client.get("/me", headers=bearer("not.a.token"))
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_TOKEN_INVALID"


async def test_expired_token(client, make_user):
    uid, name = make_user()
    now = int(time.time())
    old = jwt.encode({"sub": str(uid), "username": name, "role": "ADMIN", "iss": "agent-governance-platform",
                      "iat": now - 7200, "exp": now - 3600}, "j" * 40, algorithm="HS256")
    r = await client.get("/me", headers=bearer(old))
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_TOKEN_EXPIRED"


async def test_token_for_unknown_user_is_invalid(client):
    r = await client.get("/me", headers=bearer(token_for(uuid.uuid4(), "ghost")))
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_TOKEN_INVALID"


async def test_deactivated_user_is_rejected_even_with_a_valid_token(client, make_user):
    uid, name = make_user(active=False)
    r = await client.get("/me", headers=bearer(token_for(uid, name)))
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_TOKEN_INVALID"


async def test_deactivating_a_user_takes_effect_immediately(client, make_user, engine):
    uid, name = make_user()
    token = token_for(uid, name)
    assert (await client.get("/me", headers=bearer(token))).status_code == 200
    with engine.begin() as c:
        c.execute(text("UPDATE users SET is_active=false WHERE user_id=:i"), {"i": uid})
    assert (await client.get("/me", headers=bearer(token))).status_code == 401


async def test_role_comes_from_the_database_not_the_token(client, make_user):
    uid, name = make_user("VIEWER")
    forged_claim = token_for(uid, name, "ADMIN")  # token says ADMIN, database says VIEWER
    me = await client.get("/me", headers=bearer(forged_claim))
    assert me.json()["role"] == "VIEWER"
    r = await client.get("/admin-only", headers=bearer(forged_claim))
    assert r.status_code == 403 and r.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"


async def test_role_change_takes_effect_immediately(client, make_user, engine):
    uid, name = make_user("VIEWER")
    token = token_for(uid, name, "VIEWER")
    assert (await client.get("/admin-only", headers=bearer(token))).status_code == 403
    with engine.begin() as c:
        c.execute(text("UPDATE users SET role='ADMIN' WHERE user_id=:i"), {"i": uid})
    assert (await client.get("/admin-only", headers=bearer(token))).status_code == 200


@pytest.mark.parametrize("role,status", [("ADMIN", 200), ("REVIEWER", 200), ("OPERATOR", 403), ("VIEWER", 403)])
async def test_require_roles_with_two_allowed_roles(client, make_user, role, status):
    uid, name = make_user(role)
    r = await client.get("/staff", headers=bearer(token_for(uid, name, role)))
    assert r.status_code == status


async def test_protected_route_without_login_is_401_not_403(client):
    r = await client.get("/admin-only")
    assert r.status_code == 401
