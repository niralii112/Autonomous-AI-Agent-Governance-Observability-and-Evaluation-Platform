"""Integration tests run against a REAL PostgreSQL database.

They WIPE the public schema of TEST_DATABASE_URL, so never point it at your
development database. Use a separate database, for example governance_test.
If TEST_DATABASE_URL is not set, these tests are skipped.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.integration


def run_alembic(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": TEST_URL,
        "POSTGRES_PASSWORD": "test",
        "JWT_SECRET_KEY": "j" * 40,
        "EXECUTION_GRANT_SECRET": "g" * 40,
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def engine():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_engine(TEST_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    result = run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    yield eng
    eng.dispose()


@pytest.fixture
def conn(engine):
    """A connection inside a transaction that is rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()
