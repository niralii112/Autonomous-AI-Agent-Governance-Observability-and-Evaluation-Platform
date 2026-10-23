"""Login, current user and logout (spec section 18)."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, AuditEventName, AuditOutcome, ErrorCode
from app.core.exceptions import AppError
from app.core.security import (
    access_token_lifetime_seconds,
    burn_password_check,
    create_access_token,
    verify_password,
)
from app.core.enums import UserRole
from app.repositories import user_repository
from app.schemas import ActorContext, AuditEventCreate, LoginRequest, TokenResponse, UserResponse
from app.services.audit_service import record_audit_event


def _invalid_credentials() -> AppError:
    # One message for every failure: unknown user, wrong password, inactive user.
    return AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid username or password.")


async def login(session: AsyncSession, request: LoginRequest) -> TokenResponse:
    """Raises AUTH_INVALID_CREDENTIALS for any failure and records an audit event either way.
    The caller must commit even when this raises, so the failure audit row is kept."""
    user = await user_repository.get_by_username(session, request.username)

    if user is None:
        burn_password_check(request.password)  # same time as a real check
        password_ok = False
    else:
        password_ok = verify_password(request.password, user.password_hash)

    if user is None or not password_ok or not user.is_active:
        await record_audit_event(
            session,
            AuditEventCreate(
                event_name=AuditEventName.AUTH_LOGIN_FAILED,
                actor_type=ActorType.USER,
                actor_user_id=user.user_id if user is not None else None,
                entity_type="user",
                entity_id=user.user_id if user is not None else None,
                outcome=AuditOutcome.FAILURE,
                event_data={"username": request.username[:64]},  # never the password
            ),
        )
        raise _invalid_credentials()

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(user)
    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=AuditEventName.AUTH_LOGIN_SUCCEEDED,
            actor_type=ActorType.USER,
            actor_user_id=user.user_id,
            entity_type="user",
            entity_id=user.user_id,
            outcome=AuditOutcome.SUCCESS,
            event_data={"username": user.username},
        ),
    )
    return TokenResponse(
        access_token=create_access_token(user.user_id, user.username, UserRole(user.role)),
        token_type="bearer",
        expires_in=access_token_lifetime_seconds(),
        user=UserResponse.model_validate(user),
    )


async def get_current_user(session: AsyncSession, actor: ActorContext) -> UserResponse:
    user = await user_repository.get_by_id(session, actor.user_id)
    if user is None:  # deleted between the dependency check and now
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "The access token is not valid.")
    return UserResponse.model_validate(user)


async def logout(session: AsyncSession, actor: ActorContext) -> None:
    """Tokens are stateless: the client discards the token. We only record the event."""
    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=AuditEventName.AUTH_LOGOUT,
            actor_type=ActorType.USER,
            actor_user_id=actor.user_id,
            entity_type="user",
            entity_id=actor.user_id,
            outcome=AuditOutcome.SUCCESS,
            event_data={},
        ),
    )
