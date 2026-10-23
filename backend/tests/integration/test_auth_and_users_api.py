"""AUTH-01..03 and USR-01..03 through the real app and a real PostgreSQL database."""

import time

import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import security
from app.core.config import get_settings
from app.core.database import get_session
from app.main import create_app
from app.schemas import AuditEventResponse, ErrorResponse, TokenResponse, UserResponse, UserResponsePage
from tests.integration.conftest import TEST_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]

PASSWORD = "Correct-Horse-12"
JWT_SECRET = "j" * 40


@pytest.fixture(autouse=True)
def env(monkeypatch, engine):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", TEST_URL or "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)
    get_settings.cache_clear()
    with engine.begin() as c:  # audit_events is append-only, TRUNCATE is the way to reset it
        c.execute(text("TRUNCATE users, audit_events RESTART IDENTITY CASCADE"))
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
    def make(username, role="VIEWER", active=True, password=PASSWORD, email=None):
        rows = db(
            "INSERT INTO users (username,email,password_hash,role,is_active) "
            "VALUES (:u,:e,:h,:r,:a) RETURNING user_id",
            u=username, e=email or f"{username}@x.test", h=security.hash_password(password), r=role, a=active,
        )
        return rows[0]["user_id"]

    return make


async def login(client, username, password=PASSWORD):
    return await client.post("/api/v1/auth/login", json={"username": username, "password": password})


async def token_of(client, username, password=PASSWORD):
    r = await login(client, username, password)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def admin_headers(client, make_user, name="boss"):
    make_user(name, "ADMIN")
    return auth(await token_of(client, name))


def audit_rows(db, event_name=None):
    sql = "SELECT * FROM audit_events"
    if event_name:
        return db(sql + " WHERE event_name=:n ORDER BY created_at", n=event_name)
    return db(sql + " ORDER BY created_at")


# ================================ AUTH-01 login ===================================================

async def test_login_success_matches_contract(client, make_user, db):
    uid = make_user("nirali", "REVIEWER")
    r = await login(client, "nirali")
    assert r.status_code == 200
    body = TokenResponse.model_validate(r.json())
    assert body.token_type == "bearer" and body.expires_in == 3600
    assert body.user.username == "nirali" and body.user.role.value == "REVIEWER"
    assert "password" not in r.text and "password_hash" not in r.text
    claims = jwt.decode(body.access_token, JWT_SECRET, algorithms=["HS256"], issuer="agent-governance-platform")
    assert claims["sub"] == str(uid) and claims["role"] == "REVIEWER" and claims["username"] == "nirali"
    assert db("SELECT last_login_at FROM users WHERE user_id=:i", i=uid)[0]["last_login_at"] is not None


async def test_login_success_is_audited(client, make_user, db):
    uid = make_user("nirali")
    await login(client, "nirali")
    rows = audit_rows(db, "AUTH_LOGIN_SUCCEEDED")
    assert len(rows) == 1 and rows[0]["actor_user_id"] == uid and rows[0]["outcome"] == "SUCCESS"
    AuditEventResponse.model_validate(dict(rows[0]))


@pytest.mark.parametrize("case", ["wrong_password", "unknown_user", "inactive_user"])
async def test_every_login_failure_looks_the_same(client, make_user, db, case):
    make_user("realuser")
    make_user("sleeper", active=False)
    attempts = {
        "wrong_password": ("realuser", "Wrong-Password-1"),
        "unknown_user": ("nobody", PASSWORD),
        "inactive_user": ("sleeper", PASSWORD),  # correct password, but inactive
    }
    r = await login(client, *attempts[case])
    assert r.status_code == 401
    body = ErrorResponse.model_validate(r.json())
    assert body.error_code.value == "AUTH_INVALID_CREDENTIALS"
    assert body.error_message == "Invalid username or password."
    assert body.details is None  # nothing that reveals which part was wrong


async def test_failed_logins_are_audited_and_kept(client, make_user, db):
    make_user("realuser")
    await login(client, "realuser", "Wrong-Password-1")
    await login(client, "nobody", "Another-Wrong-Pw-1")
    rows = audit_rows(db, "AUTH_LOGIN_FAILED")
    assert len(rows) == 2 and all(r["outcome"] == "FAILURE" for r in rows)
    assert rows[0]["actor_user_id"] is not None and rows[1]["actor_user_id"] is None
    text_dump = str([dict(r) for r in rows])
    assert "Wrong-Password-1" not in text_dump and "Another-Wrong-Pw-1" not in text_dump


@pytest.mark.parametrize("payload", [
    {}, {"username": "a"}, {"password": "x"}, {"username": "", "password": "x"},
    {"username": "a", "password": "x" * 129}, {"username": "a" * 65, "password": "x"},
    {"username": "a", "password": "x", "is_admin": True},
])
async def test_login_rejects_bad_requests(client, payload):
    r = await client.post("/api/v1/auth/login", json=payload)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_128_character_password_can_log_in(client, make_user):
    long_password = "p" * 128
    make_user("longpw", password=long_password)
    assert (await login(client, "longpw", long_password)).status_code == 200
    assert (await login(client, "longpw", "p" * 127)).status_code == 401


# ================================ AUTH-02 me, AUTH-03 logout ======================================

async def test_me_returns_the_logged_in_user(client, make_user):
    make_user("nirali", "OPERATOR")
    r = await client.get("/api/v1/auth/me", headers=auth(await token_of(client, "nirali")))
    assert r.status_code == 200
    assert UserResponse.model_validate(r.json()).username == "nirali"
    assert "password" not in r.text


async def test_me_without_token_is_401(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error_code"] == "AUTH_MISSING_CREDENTIALS"


async def test_logout_returns_204_and_is_audited(client, make_user, db):
    uid = make_user("nirali")
    r = await client.post("/api/v1/auth/logout", headers=auth(await token_of(client, "nirali")))
    assert r.status_code == 204 and r.content == b""
    rows = audit_rows(db, "AUTH_LOGOUT")
    assert len(rows) == 1 and rows[0]["actor_user_id"] == uid


async def test_logout_needs_a_token(client):
    assert (await client.post("/api/v1/auth/logout")).status_code == 401


# ================================ USR access control ===============================================

@pytest.mark.parametrize("role", ["REVIEWER", "OPERATOR", "VIEWER"])
async def test_only_admin_can_use_the_users_api(client, make_user, role):
    target = make_user("target")
    make_user("someone", role)
    h = auth(await token_of(client, "someone"))
    body = {"username": "newuser", "email": "n@x.test", "password": PASSWORD, "role": "VIEWER"}
    for response in (
        await client.get("/api/v1/users", headers=h),
        await client.post("/api/v1/users", json=body, headers=h),
        await client.patch(f"/api/v1/users/{target}", json={"role": "ADMIN"}, headers=h),
    ):
        assert response.status_code == 403 and response.json()["error_code"] == "AUTH_INSUFFICIENT_ROLE"


async def test_users_api_needs_login(client):
    assert (await client.get("/api/v1/users")).status_code == 401


# ================================ USR-02 create ====================================================

def new_user_body(**kw):
    return {**{"username": "newuser", "email": "new@x.test", "password": "Brand-New-Pass-1", "role": "OPERATOR"}, **kw}


async def test_create_user(client, make_user, db):
    h = await admin_headers(client, make_user)
    r = await client.post("/api/v1/users", json=new_user_body(), headers=h)
    assert r.status_code == 201
    created = UserResponse.model_validate(r.json())
    assert created.role.value == "OPERATOR" and created.is_active is True and created.last_login_at is None
    assert "password" not in r.text

    stored = db("SELECT password_hash FROM users WHERE username='newuser'")[0]["password_hash"]
    assert stored.startswith("$2b$") and "Brand-New-Pass-1" not in stored
    assert (await login(client, "newuser", "Brand-New-Pass-1")).status_code == 200  # can log in right away


async def test_create_user_is_audited_without_the_password(client, make_user, db):
    h = await admin_headers(client, make_user)
    r = await client.post("/api/v1/users", json=new_user_body(), headers=h)
    rows = audit_rows(db, "USER_CREATED")
    assert len(rows) == 1
    assert str(rows[0]["entity_id"]) == r.json()["user_id"] and rows[0]["actor_type"] == "USER"
    assert "Brand-New-Pass-1" not in str(dict(rows[0]))


async def test_duplicate_username_and_email_are_409(client, make_user):
    h = await admin_headers(client, make_user)
    assert (await client.post("/api/v1/users", json=new_user_body(), headers=h)).status_code == 201
    same_name = await client.post("/api/v1/users", json=new_user_body(email="other@x.test"), headers=h)
    same_mail = await client.post("/api/v1/users", json=new_user_body(username="other"), headers=h)
    for r in (same_name, same_mail):
        assert r.status_code == 409 and r.json()["error_code"] == "DUPLICATE_RESOURCE"
    assert same_name.json()["details"][0]["field"] == "username"
    assert same_mail.json()["details"][0]["field"] == "email"


@pytest.mark.parametrize("override", [
    {"password": "short-11-chr"[:11]}, {"role": "SUPERUSER"}, {"username": ""}, {"extra": 1},
])
async def test_create_user_validation(client, make_user, override):
    h = await admin_headers(client, make_user)
    r = await client.post("/api/v1/users", json=new_user_body(**override), headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


# ================================ USR-01 list ======================================================

async def test_list_users_pages_and_filters(client, make_user):
    h = await admin_headers(client, make_user, "boss")
    for i in range(4):
        make_user(f"viewer{i}", "VIEWER", active=(i != 0))
    make_user("rev", "REVIEWER")

    r = await client.get("/api/v1/users", params={"page_size": 2, "sort_by": "username", "sort_order": "asc"}, headers=h)
    page = UserResponsePage.model_validate(r.json())
    assert [u.username for u in page.items] == ["boss", "rev"]
    assert (page.page, page.page_size, page.total_items, page.total_pages) == (1, 2, 6, 3)
    assert "password" not in r.text

    last = await client.get("/api/v1/users", params={"page": 3, "page_size": 2, "sort_by": "username", "sort_order": "asc"}, headers=h)
    assert [u["username"] for u in last.json()["items"]] == ["viewer2", "viewer3"]

    viewers = (await client.get("/api/v1/users", params={"role": "VIEWER"}, headers=h)).json()
    assert viewers["total_items"] == 4
    inactive = (await client.get("/api/v1/users", params={"is_active": "false"}, headers=h)).json()
    assert [u["username"] for u in inactive["items"]] == ["viewer0"]


async def test_list_default_is_newest_first(client, make_user):
    h = await admin_headers(client, make_user, "boss")
    make_user("zzz-newest")
    names = [u["username"] for u in (await client.get("/api/v1/users", headers=h)).json()["items"]]
    assert names[0] == "zzz-newest"


@pytest.mark.parametrize("params", [{"sort_by": "password_hash"}, {"page_size": 101}, {"page": 0}, {"role": "BOSS"}, {"sort_order": "up"}])
async def test_list_rejects_bad_query(client, make_user, params):
    h = await admin_headers(client, make_user)
    r = await client.get("/api/v1/users", params=params, headers=h)
    assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"


async def test_empty_list_has_zero_pages(client, make_user):
    h = await admin_headers(client, make_user)
    body = (await client.get("/api/v1/users", params={"role": "REVIEWER"}, headers=h)).json()
    assert body["items"] == [] and body["total_items"] == 0 and body["total_pages"] == 0


# ================================ USR-03 update ====================================================

async def test_update_email_and_role(client, make_user, db):
    h = await admin_headers(client, make_user)
    uid = make_user("target", "VIEWER")
    r = await client.patch(f"/api/v1/users/{uid}", json={"email": "changed@x.test", "role": "REVIEWER"}, headers=h)
    assert r.status_code == 200
    body = UserResponse.model_validate(r.json())
    assert body.email == "changed@x.test" and body.role.value == "REVIEWER"
    assert body.updated_at >= body.created_at
    event = audit_rows(db, "USER_UPDATED")[0]
    assert event["event_data"]["changed_fields"] == ["email", "role"]
    assert event["event_data"]["role_from"] == "VIEWER" and event["event_data"]["role_to"] == "REVIEWER"


async def test_password_change_works_and_is_never_logged(client, make_user, db):
    h = await admin_headers(client, make_user)
    uid = make_user("target")
    r = await client.patch(f"/api/v1/users/{uid}", json={"password": "A-Brand-New-Pass-9"}, headers=h)
    assert r.status_code == 200
    assert (await login(client, "target", PASSWORD)).status_code == 401
    assert (await login(client, "target", "A-Brand-New-Pass-9")).status_code == 200
    event = audit_rows(db, "USER_UPDATED")[0]
    assert event["event_data"] == {"changed_fields": ["password"]}
    assert "A-Brand-New-Pass-9" not in str(dict(event))


async def test_deactivating_blocks_login_and_existing_tokens(client, make_user):
    h = await admin_headers(client, make_user)
    uid = make_user("target")
    old_token = await token_of(client, "target")
    assert (await client.patch(f"/api/v1/users/{uid}", json={"is_active": False}, headers=h)).status_code == 200
    assert (await login(client, "target")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=auth(old_token))).status_code == 401


async def test_role_change_applies_to_a_token_already_issued(client, make_user):
    h = await admin_headers(client, make_user)
    uid = make_user("target", "REVIEWER")
    token = await token_of(client, "target")
    assert (await client.get("/api/v1/users", headers=auth(token))).status_code == 403
    await client.patch(f"/api/v1/users/{uid}", json={"role": "ADMIN"}, headers=h)
    assert (await client.get("/api/v1/users", headers=auth(token))).status_code == 200


async def test_empty_or_unchanged_update_changes_nothing_and_logs_nothing(client, make_user, db):
    h = await admin_headers(client, make_user)
    uid = make_user("target", "VIEWER", email="same@x.test")
    for body in ({}, {"role": "VIEWER", "email": "same@x.test"}, {"password": None, "email": None}):
        r = await client.patch(f"/api/v1/users/{uid}", json=body, headers=h)
        assert r.status_code == 200 and r.json()["role"] == "VIEWER"
    assert audit_rows(db, "USER_UPDATED") == []


async def test_update_unknown_user_is_404(client, make_user):
    h = await admin_headers(client, make_user)
    r = await client.patch("/api/v1/users/00000000-0000-4000-8000-000000000000", json={"role": "ADMIN"}, headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"


async def test_update_with_a_taken_email_is_409(client, make_user):
    h = await admin_headers(client, make_user)
    make_user("first", email="taken@x.test")
    uid = make_user("second")
    r = await client.patch(f"/api/v1/users/{uid}", json={"email": "taken@x.test"}, headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "DUPLICATE_RESOURCE"


@pytest.mark.parametrize("body", [{"password": "short"}, {"role": "BOSS"}, {"is_active": "maybe"}, {"unknown": 1}])
async def test_update_validation(client, make_user, body):
    h = await admin_headers(client, make_user)
    uid = make_user("target")
    r = await client.patch(f"/api/v1/users/{uid}", json=body, headers=h)
    assert r.status_code == 422


async def test_bad_user_id_in_path_is_422(client, make_user):
    h = await admin_headers(client, make_user)
    assert (await client.patch("/api/v1/users/not-a-uuid", json={}, headers=h)).status_code == 422


# ================================ contract examples ================================================

async def test_contract_example_request_is_accepted(client, make_user):
    import json
    from pathlib import Path

    example = json.loads((Path(__file__).resolve().parents[3] / "contracts/examples/USR-02.request.json").read_text())
    h = await admin_headers(client, make_user)
    r = await client.post("/api/v1/users", json=example, headers=h)
    assert r.status_code == 201
    assert set(r.json()) == set(json.loads((Path(__file__).resolve().parents[3] / "contracts/examples/USR-02.response.json").read_text()))


async def test_audit_event_records_the_trace_id_when_a_span_is_active(client, make_user, db):
    from opentelemetry.sdk.trace import TracerProvider

    make_user("nirali")
    with TracerProvider().get_tracer("t").start_as_current_span("login"):
        await login(client, "nirali")
    trace_id = audit_rows(db, "AUTH_LOGIN_SUCCEEDED")[0]["trace_id"]
    assert trace_id is not None and len(trace_id) == 32
