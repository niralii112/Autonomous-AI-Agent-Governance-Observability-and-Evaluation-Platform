"""Authentication and role checks for routers (spec section 18).

The role is read from the database on every request, not trusted from the token, so a
role change or a deactivated user takes effect immediately.
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.enums import ErrorCode, UserRole
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas import ActorContext

_bearer = HTTPBearer(auto_error=False)


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> ActorContext:
    if credentials is None or not credentials.credentials:
        raise AppError(ErrorCode.AUTH_MISSING_CREDENTIALS, "Authentication is required.")
    claims = decode_access_token(credentials.credentials)

    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "The access token is not valid.")
    return ActorContext(user_id=user.user_id, username=user.username, role=UserRole(user.role))


def require_roles(*allowed: UserRole) -> Callable[..., Awaitable[ActorContext]]:
    """Dependency factory: `Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))`."""

    async def checker(actor: ActorContext = Depends(get_current_actor)) -> ActorContext:
        if actor.role not in allowed:
            raise AppError(
                ErrorCode.AUTH_INSUFFICIENT_ROLE,
                "Your role is not allowed to do this.",
            )
        return actor

    return checker
