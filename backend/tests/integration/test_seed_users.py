import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core import security
from app.core.config import Settings
from tests.integration.conftest import TEST_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]

SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
spec = importlib.util.spec_from_file_location("seed_script", SEED_PATH)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


def settings(**kw):
    values = dict(
        postgres_password="x", database_url="postgresql+psycopg://u:x@localhost/db",
        jwt_secret_key="j" * 40, execution_grant_secret="g" * 40, app_env="test",
        seed_admin_password="Admin-Seed-Pass-1", seed_reviewer_password="Reviewer-Seed-Pw-1",
        seed_operator_password="Operator-Seed-Pw-1", seed_viewer_password="Viewer-Seed-Pass-1",
    )
    values.update(kw)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def clean(engine, monkeypatch):
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)
    with engine.begin() as c:
        c.execute(text("TRUNCATE users, audit_events RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session_factory():
    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


async def run(session_factory, cfg):
    async with session_factory() as s:
        result = await seed.seed_users(s, cfg)
        await s.commit()
    return result


async def test_creates_the_four_users_with_the_right_roles(session_factory, engine):
    result = await run(session_factory, settings())
    assert result == {"admin": "created", "reviewer": "created", "operator": "created", "viewer": "created"}
    with engine.connect() as c:
        rows = {r.username: r for r in c.execute(text("SELECT username, role, password_hash, is_active FROM users"))}
    assert {u: r.role for u, r in rows.items()} == {
        "admin": "ADMIN", "reviewer": "REVIEWER", "operator": "OPERATOR", "viewer": "VIEWER"}
    assert all(r.is_active for r in rows.values())
    assert security.verify_password("Admin-Seed-Pass-1", rows["admin"].password_hash)
    assert security.verify_password("Viewer-Seed-Pass-1", rows["viewer"].password_hash)


async def test_running_twice_changes_nothing(session_factory, engine):
    await run(session_factory, settings())
    again = await run(session_factory, settings(seed_admin_password="Different-Password-2"))
    assert set(again.values()) == {"exists"}
    with engine.connect() as c:
        h = c.execute(text("SELECT password_hash FROM users WHERE username='admin'")).scalar_one()
        events = c.execute(text("SELECT count(*) FROM audit_events WHERE event_name='USER_CREATED'")).scalar_one()
    assert security.verify_password("Admin-Seed-Pass-1", h)  # old password kept
    assert events == 4


async def test_seeding_is_audited_as_system(session_factory, engine):
    await run(session_factory, settings())
    with engine.connect() as c:
        rows = list(c.execute(text("SELECT actor_type, actor_user_id, event_data FROM audit_events")))
    assert len(rows) == 4 and all(r.actor_type == "SYSTEM" and r.actor_user_id is None for r in rows)
    assert all(r.event_data["source"] == "seed" for r in rows)


@pytest.mark.parametrize("bad", [None, "", "short-pw-11"])
async def test_missing_or_short_password_stops_the_seed(session_factory, bad):
    with pytest.raises(SystemExit):
        await run(session_factory, settings(seed_viewer_password=bad))


async def test_placeholder_password_is_refused_outside_local_and_test(session_factory):
    cfg = settings(app_env="production", seed_admin_password="CHANGE_ME_SEED_ADMIN")
    with pytest.raises(SystemExit):
        await run(session_factory, cfg)
