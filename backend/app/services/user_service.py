"""User administration (USR-01..03). ADMIN only, enforced here again after the router."""

import math
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, AuditEventName, AuditOutcome, ErrorCode, SortOrder, UserRole
from app.core.exceptions import AppError, DuplicateResourceError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories import user_repository
from app.schemas import (
    ActorContext,
    AuditEventCreate,
    UserCreateRequest,
    UserResponse,
    UserResponsePage,
    UserUpdateRequest,
)
from app.services.audit_service import record_audit_event


def _require_admin(actor: ActorContext) -> None:
    if actor.role != UserRole.ADMIN:
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")


async def list_users(
    session: AsyncSession,
    actor: ActorContext,
    *,
    role: UserRole | None,
    is_active: bool | None,
    page: int,
    page_size: int,
    sort_by: user_repository.SortField,
    sort_order: SortOrder,
) -> UserResponsePage:
    _require_admin(actor)
    rows, total = await user_repository.list_users(
        session,
        role=role.value if role else None,
        is_active=is_active,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        descending=sort_order == SortOrder.desc,
    )
    return UserResponsePage(
        items=[UserResponse.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size),
    )


async def create_user(session: AsyncSession, request: UserCreateRequest, actor: ActorContext) -> UserResponse:
    _require_admin(actor)
    if await user_repository.get_by_username(session, request.username):
        raise DuplicateResourceError("A user with this username already exists.", {"username": "already exists"})
    if await user_repository.get_by_email(session, request.email):
        raise DuplicateResourceError("A user with this email already exists.", {"email": "already exists"})

    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role.value,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:  # two requests raced past the checks above
        raise DuplicateResourceError("A user with these unique values already exists.") from None
    await session.refresh(user)

    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=AuditEventName.USER_CREATED,
            actor_type=ActorType.USER,
            actor_user_id=actor.user_id,
            entity_type="user",
            entity_id=user.user_id,
            outcome=AuditOutcome.SUCCESS,
            event_data={"username": user.username, "role": user.role},
        ),
    )
    return UserResponse.model_validate(user)


async def update_user(
    session: AsyncSession, user_id: uuid.UUID, request: UserUpdateRequest, actor: ActorContext
) -> UserResponse:
    _require_admin(actor)
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("User not found.")

    # Only fields the caller actually sent (and not null) are changed.
    sent = {f: getattr(request, f) for f in request.model_fields_set if getattr(request, f) is not None}
    data: dict[str, object] = {}

    if "email" in sent and sent["email"] != user.email:
        other = await user_repository.get_by_email(session, sent["email"])
        if other is not None and other.user_id != user.user_id:
            raise DuplicateResourceError("A user with this email already exists.", {"email": "already exists"})
        user.email = sent["email"]
        data["changed_fields"] = [*data.get("changed_fields", []), "email"]
    if "role" in sent and sent["role"].value != user.role:
        data["role_from"], data["role_to"] = user.role, sent["role"].value
        user.role = sent["role"].value
        data["changed_fields"] = [*data.get("changed_fields", []), "role"]
    if "is_active" in sent and sent["is_active"] != user.is_active:
        user.is_active = sent["is_active"]
        data["changed_fields"] = [*data.get("changed_fields", []), "is_active"]
    if "password" in sent:
        user.password_hash = hash_password(sent["password"])
        data["changed_fields"] = [*data.get("changed_fields", []), "password"]  # the name only, never the value

    if data:
        try:
            await session.flush()
        except IntegrityError:
            raise DuplicateResourceError("A user with these unique values already exists.") from None
        await session.refresh(user)
        await record_audit_event(
            session,
            AuditEventCreate(
                event_name=AuditEventName.USER_UPDATED,
                actor_type=ActorType.USER,
                actor_user_id=actor.user_id,
                entity_type="user",
                entity_id=user.user_id,
                outcome=AuditOutcome.SUCCESS,
                event_data=data,
            ),
        )
    return UserResponse.model_validate(user)
