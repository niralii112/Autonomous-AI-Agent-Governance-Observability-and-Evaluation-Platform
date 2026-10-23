"""AUTH-01..03 (spec section 11.2)."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.exceptions import AppError
from app.dependencies.auth import get_current_actor
from app.schemas import ActorContext, LoginRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["AUTH"])


@router.post(
    "/login",
    response_model=TokenResponse,
    operation_id="loginUser",
    summary="Obtain access token",
    responses=errors(401, 422, 503),
)
async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    try:
        result = await auth_service.login(session, request)
    except AppError:
        await session.commit()  # keep the AUTH_LOGIN_FAILED audit row
        raise
    await session.commit()
    return result


@router.get(
    "/me",
    response_model=UserResponse,
    operation_id="getCurrentUser",
    summary="Current user",
    responses=errors(401, 403),
)
async def me(
    actor: ActorContext = Depends(get_current_actor), session: AsyncSession = Depends(get_session)
) -> UserResponse:
    return await auth_service.get_current_user(session, actor)


@router.post(
    "/logout",
    status_code=204,
    operation_id="logoutUser",
    summary="Record logout (token discarded client-side)",
    responses=errors(401, 403),
)
async def logout(
    actor: ActorContext = Depends(get_current_actor), session: AsyncSession = Depends(get_session)
) -> Response:
    await auth_service.logout(session, actor)
    await session.commit()
    return Response(status_code=204)
