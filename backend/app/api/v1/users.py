"""USR-01..03 (spec section 11.2). ADMIN only."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import SortOrder, UserRole
from app.dependencies.auth import require_roles
from app.schemas import ActorContext, UserCreateRequest, UserResponse, UserResponsePage, UserUpdateRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["USR"])
admin_only = require_roles(UserRole.ADMIN)


@router.get(
    "",
    response_model=UserResponsePage,
    operation_id="listUsers",
    summary="List users",
    responses=errors(401, 403),
)
async def list_users(
    role: UserRole | None = Query(None, description="Filter"),
    is_active: bool | None = Query(None, description="Filter"),
    page: int = Query(1, ge=1, le=1000000, description="1-based page"),
    page_size: int = Query(25, ge=1, le=100, description="default 25"),
    sort_by: Literal["created_at", "username"] = Query("created_at", description="one of: created_at, username"),
    sort_order: SortOrder = Query(SortOrder.desc, description="default desc"),
    actor: ActorContext = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> UserResponsePage:
    return await user_service.list_users(
        session, actor, role=role, is_active=is_active, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    operation_id="createUser",
    summary="Create user",
    responses=errors(401, 403, 409, 422),
)
async def create_user(
    request: UserCreateRequest,
    actor: ActorContext = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    result = await user_service.create_user(session, request, actor)
    await session.commit()
    return result


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    operation_id="updateUser",
    summary="Update user",
    responses=errors(401, 403, 404, 422),
)
async def update_user(
    user_id: uuid.UUID,
    request: UserUpdateRequest,
    actor: ActorContext = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    result = await user_service.update_user(session, user_id, request, actor)
    await session.commit()
    return result
