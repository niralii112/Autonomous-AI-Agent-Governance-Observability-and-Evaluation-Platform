import pytest
from sqlalchemy import text

from app.core import database
from app.core.config import get_settings
from tests.integration.conftest import TEST_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture(autouse=True)
def point_settings_at_test_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    for fn in (get_settings, database.get_engine, database.get_session_factory):
        fn.cache_clear()
    yield
    for fn in (get_settings, database.get_engine, database.get_session_factory):
        fn.cache_clear()


async def test_get_session_runs_a_query():
    gen = database.get_session()
    session = await gen.__anext__()
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
    await gen.aclose()


def test_engine_is_created_once():
    assert database.get_engine() is database.get_engine()


def test_session_factory_does_not_expire_on_commit():
    assert database.get_session_factory().kw["expire_on_commit"] is False
