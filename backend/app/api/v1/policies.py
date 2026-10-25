"""POL-01..05 (spec section 11.2). POL-06 (dry-run evaluation) comes with the policy engine."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import PolicyEffect, SortOrder, UserRole
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import (
    ActorContext, PolicyActivationRequest, PolicyCreateRequest, PolicyResponse, PolicyResponsePage,
    PolicyVersionCreateRequest,
)
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["POL"])
admin_only = require_roles(UserRole.ADMIN)


@router.post("", response_model=PolicyResponse, status_code=201, operation_id="createPolicy",
             summary="Create policy (version 1)", responses=errors(401, 403, 409, 422))
async def create_policy(request: PolicyCreateRequest, actor: ActorContext = Depends(admin_only),
                        session: AsyncSession = Depends(get_session)) -> PolicyResponse:
    result = await policy_service.create_policy(session, request, actor)
    await session.commit()
    return result


@router.get("", response_model=PolicyResponsePage, operation_id="listPolicies",
            summary="List policies", responses=errors(401, 403))
async def list_policies(
    effect: PolicyEffect | None = Query(None),
    is_active: bool | None = Query(None),
    policy_key: str | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "priority", "policy_key"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> PolicyResponsePage:
    return await policy_service.list_policies(
        session, effect=effect, is_active=is_active, policy_key=policy_key, page=page,
        page_size=page_size, sort_by=sort_by, sort_order=sort_order)


@router.get("/{policy_id}", response_model=PolicyResponse, operation_id="getPolicy",
            summary="Get policy version", responses=errors(401, 403, 404))
async def get_policy(policy_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                     session: AsyncSession = Depends(get_session)) -> PolicyResponse:
    return await policy_service.get_policy(session, policy_id)


@router.post("/{policy_id}/versions", response_model=PolicyResponse, status_code=201,
             operation_id="createPolicyVersion", summary="Create next version (deactivates previous)",
             responses=errors(401, 403, 404, 422))
async def create_policy_version(policy_id: uuid.UUID, request: PolicyVersionCreateRequest,
                                actor: ActorContext = Depends(admin_only),
                                session: AsyncSession = Depends(get_session)) -> PolicyResponse:
    result = await policy_service.create_policy_version(session, policy_id, request, actor)
    await session.commit()
    return result


@router.patch("/{policy_id}/activation", response_model=PolicyResponse, operation_id="updatePolicyActivation",
              summary="Activate or deactivate a version", responses=errors(401, 403, 404, 409))
async def update_policy_activation(policy_id: uuid.UUID, request: PolicyActivationRequest,
                                   actor: ActorContext = Depends(admin_only),
                                   session: AsyncSession = Depends(get_session)) -> PolicyResponse:
    result = await policy_service.set_policy_activation(session, policy_id, request, actor)
    await session.commit()
    return result
