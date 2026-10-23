"""Seed data for local development. Safe to run many times: existing rows are left alone.

Run from the backend folder:   python scripts/seed.py

Step 7 seeds the four users. Agents, tools, permissions and policies are added in the
registry steps.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.core.enums import ActorType, AuditEventName, AuditOutcome, UserRole  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories import user_repository  # noqa: E402
from app.schemas import AuditEventCreate  # noqa: E402
from app.services.audit_service import record_audit_event  # noqa: E402

MIN_PASSWORD_LENGTH = 12  # spec section 18

# username, email, role, name of the Settings field that holds the password
SEED_USERS = [
    ("admin", "admin@example.test", UserRole.ADMIN, "seed_admin_password"),
    ("reviewer", "reviewer@example.test", UserRole.REVIEWER, "seed_reviewer_password"),
    ("operator", "operator@example.test", UserRole.OPERATOR, "seed_operator_password"),
    ("viewer", "viewer@example.test", UserRole.VIEWER, "seed_viewer_password"),
]


def _password_for(settings: Settings, username: str, field: str) -> str:
    value = getattr(settings, field)
    env_name = field.upper()
    if not value:
        raise SystemExit(f"{env_name} is not set. Put it in .env (see .env.example).")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"{env_name} must be at least {MIN_PASSWORD_LENGTH} characters.")
    if "CHANGE_ME" in value and settings.app_env not in ("local", "test"):
        raise SystemExit(f"{env_name} still has the CHANGE_ME placeholder.")
    return value


async def seed_users(session: AsyncSession, settings: Settings) -> dict[str, str]:
    """Create the four users. Returns {username: 'created' | 'exists'}."""
    passwords = {name: _password_for(settings, name, field) for name, _, _, field in SEED_USERS}
    result: dict[str, str] = {}
    for username, email, role, _ in SEED_USERS:
        if await user_repository.get_by_username(session, username):
            result[username] = "exists"  # never overwrite an existing password
            continue
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(passwords[username]),
            role=role.value,
        )
        session.add(user)
        await session.flush()
        await record_audit_event(
            session,
            AuditEventCreate(
                event_name=AuditEventName.USER_CREATED,
                actor_type=ActorType.SYSTEM,
                entity_type="user",
                entity_id=user.user_id,
                outcome=AuditOutcome.SUCCESS,
                event_data={"username": username, "role": role.value, "source": "seed"},
            ),
        )
        result[username] = "created"
    return result


async def main() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        users = await seed_users(session, settings)
        await session.commit()
    for username, state in users.items():
        print(f"user {username}: {state}")


if __name__ == "__main__":
    asyncio.run(main())
