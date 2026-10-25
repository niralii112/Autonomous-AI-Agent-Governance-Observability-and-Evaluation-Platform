"""Policy registry (spec 12.3, 13.1; POL-01..05). evaluate_policy is added in the next step."""

import math
import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ActorType, AuditEventName, AuditOutcome, ErrorCode, PolicyEffect, SortOrder, UserRole,
)
from app.core.exceptions import AppError, DuplicateResourceError, NotFoundError
from app.models.policy import Policy
from app.repositories import agent_repository, policy_repository
from app.schemas import (
    ActorContext, AuditEventCreate, PolicyActivationRequest, PolicyCreateRequest, PolicyResponse,
    PolicyResponsePage, PolicyVersionCreateRequest,
)
from app.services.audit_service import record_audit_event
from app.services.policy_conditions import validate_conditions

POLICY_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,99}$")  # kebab-case, like the seed policies


def _require_admin(actor: ActorContext) -> None:
    if actor.role != UserRole.ADMIN:
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")


def _invalid(field: str, message: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, "Request failed validation.", {field: message})


async def _check_body(session: AsyncSession, request: PolicyCreateRequest | PolicyVersionCreateRequest) -> None:
    """Rules shared by POL-01 and POL-04."""
    if request.is_mandatory and request.effect != PolicyEffect.BLOCK:
        raise _invalid("is_mandatory", "only allowed with effect BLOCK")
    validate_conditions(request.conditions)
    if request.scope_agent_id is not None and not await agent_repository.get_by_id(session, request.scope_agent_id):
        raise _invalid("scope_agent_id", "agent not found")


async def _audit(session, actor, event, policy: Policy, data) -> None:
    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=event, actor_type=ActorType.USER, actor_user_id=actor.user_id,
            entity_type="policy", entity_id=policy.policy_id, outcome=AuditOutcome.SUCCESS, event_data=data,
        ),
    )


def _row(request, *, policy_key: str, version: int, actor: ActorContext, supersedes: uuid.UUID | None) -> Policy:
    return Policy(
        policy_key=policy_key, version=version, name=request.name, description=request.description,
        effect=request.effect.value, priority=request.priority, is_mandatory=request.is_mandatory,
        is_active=True, conditions=request.conditions.model_dump(mode="json"),
        scope_agent_id=request.scope_agent_id,
        scope_agent_category=request.scope_agent_category.value if request.scope_agent_category else None,
        scope_action_type=request.scope_action_type.value if request.scope_action_type else None,
        supersedes_policy_id=supersedes, created_by_user_id=actor.user_id,
    )


async def create_policy(session: AsyncSession, request: PolicyCreateRequest, actor: ActorContext) -> PolicyResponse:
    """POL-01: version 1, active."""
    _require_admin(actor)
    if not POLICY_KEY_PATTERN.match(request.policy_key):
        raise _invalid("policy_key", "must be kebab-case: lowercase letters, digits and hyphens, starting with a letter")
    await _check_body(session, request)
    if await policy_repository.key_exists(session, request.policy_key):
        raise DuplicateResourceError("A policy with this key already exists.", {"policy_key": "already exists"})

    policy = _row(request, policy_key=request.policy_key, version=1, actor=actor, supersedes=None)
    session.add(policy)
    try:
        await session.flush()
    except IntegrityError:
        raise DuplicateResourceError("A policy with this key already exists.") from None
    await session.refresh(policy)
    await _audit(session, actor, AuditEventName.POLICY_CREATED, policy, {
        "policy_key": policy.policy_key, "version": 1, "effect": policy.effect,
        "priority": policy.priority, "is_mandatory": policy.is_mandatory})
    return PolicyResponse.model_validate(policy)


async def create_policy_version(
    session: AsyncSession, policy_id: uuid.UUID, request: PolicyVersionCreateRequest, actor: ActorContext
) -> PolicyResponse:
    """POL-04: version n+1 of the same policy_key; the active version is deactivated in the same transaction."""
    _require_admin(actor)
    base = await policy_repository.get_by_id(session, policy_id)
    if base is None:
        raise NotFoundError("Policy not found.")
    await _check_body(session, request)

    versions = await policy_repository.lock_versions(session, base.policy_key)  # newest first
    latest = versions[0]
    deactivated = next((v for v in versions if v.is_active), None)
    if deactivated is not None:
        deactivated.is_active = False
        await session.flush()  # must happen before the insert: only one active version per key

    policy = _row(request, policy_key=base.policy_key, version=latest.version + 1, actor=actor,
                  supersedes=latest.policy_id)
    session.add(policy)
    try:
        await session.flush()
    except IntegrityError:
        raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "Another change to this policy is in progress.") from None
    await session.refresh(policy)
    await _audit(session, actor, AuditEventName.POLICY_VERSION_CREATED, policy, {
        "policy_key": policy.policy_key, "version": policy.version, "previous_version": latest.version,
        "deactivated_policy_id": str(deactivated.policy_id) if deactivated else None,
        "effect": policy.effect, "priority": policy.priority, "is_mandatory": policy.is_mandatory})
    return PolicyResponse.model_validate(policy)


async def set_policy_activation(
    session: AsyncSession, policy_id: uuid.UUID, request: PolicyActivationRequest, actor: ActorContext
) -> PolicyResponse:
    """POL-05: switch one version on or off. Only one version per policy_key may be active."""
    _require_admin(actor)
    policy = await policy_repository.get_by_id(session, policy_id)
    if policy is None:
        raise NotFoundError("Policy not found.")
    if policy.is_active == request.is_active:
        return PolicyResponse.model_validate(policy)  # nothing to change, nothing to audit

    if request.is_active:
        other = await policy_repository.get_active_for_key(session, policy.policy_key)
        if other is not None:
            raise AppError(ErrorCode.INVALID_STATE_TRANSITION,
                           "Another version of this policy is active. Deactivate it first.",
                           {"active_version": str(other.version)})
    previous = policy.is_active
    policy.is_active = request.is_active
    try:
        await session.flush()
    except IntegrityError:
        raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "Another version of this policy is active.") from None
    await session.refresh(policy)
    await _audit(session, actor, AuditEventName.POLICY_ACTIVATION_CHANGED, policy, {
        "policy_key": policy.policy_key, "version": policy.version,
        "is_active_from": previous, "is_active_to": policy.is_active})
    return PolicyResponse.model_validate(policy)


async def get_policy(session: AsyncSession, policy_id: uuid.UUID) -> PolicyResponse:
    policy = await policy_repository.get_by_id(session, policy_id)
    if policy is None:
        raise NotFoundError("Policy not found.")
    return PolicyResponse.model_validate(policy)


async def list_policies(
    session: AsyncSession, *, effect: PolicyEffect | None, is_active: bool | None, policy_key: str | None,
    page: int, page_size: int, sort_by: policy_repository.SortField, sort_order: SortOrder,
) -> PolicyResponsePage:
    rows, total = await policy_repository.list_policies(
        session, effect=effect.value if effect else None, is_active=is_active, policy_key=policy_key,
        page=page, page_size=page_size, sort_by=sort_by, descending=sort_order == SortOrder.desc)
    return PolicyResponsePage(
        items=[PolicyResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size))
