"""Policy registry (spec 12.3, 13.1; POL-01..05) and the policy engine, evaluate_policy (spec 12.4, 13.2)."""

import logging
import math
import re
import uuid
from time import perf_counter

from opentelemetry import trace
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ActorType, AuditEventName, AuditOutcome, ErrorCode, PolicyEffect, PolicyResult, SortOrder, UserRole,
)
from app.core.exceptions import AppError, DuplicateResourceError, NotFoundError
from app.models.policy import Policy
from app.repositories import agent_repository, policy_repository
from app.schemas import (
    ActorContext, AuditEventCreate, MatchedPolicy, PolicyActivationRequest, PolicyConditions, PolicyCreateRequest,
    PolicyEvaluationRequest, PolicyEvaluationResponse, PolicyResponse, PolicyResponsePage, PolicyVersionCreateRequest,
)
from app.services.audit_service import record_audit_event
from app.services import policy_matching
from app.services.policy_conditions import validate_conditions

POLICY_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,99}$")  # kebab-case, like the seed policies

logger = logging.getLogger("governance.policy")
_tracer = trace.get_tracer("governance.policy")


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


# ======================================= the policy engine (spec 12.4, 13.2) ==========================

def _error_response(started: float) -> PolicyEvaluationResponse:
    return PolicyEvaluationResponse(
        policy_result=PolicyResult.ERROR, matched_policies=[], winning_policy_id=None, conflict_detected=False,
        evaluated_policy_count=0, policy_snapshot_hash=policy_matching.snapshot_hash([]),
        error_code=ErrorCode.POLICY_ENGINE_FAILURE, latency_ms=round((perf_counter() - started) * 1000, 3))


async def _evaluate(session: AsyncSession, request: PolicyEvaluationRequest, started: float) -> PolicyEvaluationResponse:
    ctx = policy_matching.EvalContext(
        action_type=request.action_type.value, agent_id=str(request.agent_id),
        agent_category=request.agent_category.value, tool_name=request.tool_name,
        tool_sensitivity=request.tool_sensitivity.value if request.tool_sensitivity else None,
        action_payload=request.action_payload)

    evaluated = 0
    matched: list[MatchedPolicy] = []
    for policy in await policy_repository.list_active_ordered(session):  # priority, then policy_key
        if not policy_matching.scope_applies(policy.scope_agent_id, policy.scope_agent_category,
                                             policy.scope_action_type, ctx):
            continue
        evaluated += 1
        if policy_matching.conditions_match(PolicyConditions.model_validate(policy.conditions), ctx):
            matched.append(MatchedPolicy(policy_id=policy.policy_id, policy_key=policy.policy_key,
                                         version=policy.version, effect=policy.effect, priority=policy.priority,
                                         is_mandatory=policy.is_mandatory))

    result, winner = policy_matching.choose_winner(matched)
    return PolicyEvaluationResponse(
        policy_result=result, matched_policies=matched, winning_policy_id=winner.policy_id if winner else None,
        conflict_detected=policy_matching.conflict_detected(matched), evaluated_policy_count=evaluated,
        policy_snapshot_hash=policy_matching.snapshot_hash(matched), error_code=None,
        latency_ms=round((perf_counter() - started) * 1000, 3))


async def _audit_evaluation(session: AsyncSession, request: PolicyEvaluationRequest,
                            response: PolicyEvaluationResponse, reason: str | None) -> None:
    failed = response.policy_result == PolicyResult.ERROR
    data = ({"error_code": ErrorCode.POLICY_ENGINE_FAILURE.value, "reason": reason} if failed else {
        "policy_result": response.policy_result.value,
        "matched_policy_ids": [str(m.policy_id) for m in response.matched_policies],
        "winning_policy_id": str(response.winning_policy_id) if response.winning_policy_id else None,
        "conflict_detected": response.conflict_detected,
        "evaluated_policy_count": response.evaluated_policy_count,
        "policy_snapshot_hash": response.policy_snapshot_hash})
    # A savepoint, so a failed audit write cannot poison the caller's transaction.
    async with session.begin_nested():
        await record_audit_event(session, AuditEventCreate(
            event_name=AuditEventName.POLICY_EVALUATION_FAILED if failed else AuditEventName.POLICY_EVALUATED,
            actor_type=ActorType.SYSTEM, agent_id=request.agent_id, action_id=request.action_id,
            entity_type="action", entity_id=request.action_id,
            outcome=AuditOutcome.FAILURE if failed else AuditOutcome.SUCCESS, event_data=data))


async def evaluate_policy(session: AsyncSession, request: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
    """Decide what the active policies say about one proposed action.

    NEVER raises. Any internal problem (database error, malformed policy, failed audit write)
    comes back as policy_result ERROR / POLICY_ENGINE_FAILURE, which the decision engine turns
    into BLOCK. With action_id=None (dry-run) nothing is written; otherwise one audit event is."""
    started = perf_counter()
    with _tracer.start_as_current_span("policy.evaluate") as span:
        reason: str | None = None
        try:
            response = await _evaluate(session, request, started)
        except Exception as exc:  # noqa: BLE001 - the contract says this function never raises
            reason = type(exc).__name__
            logger.error("policy evaluation failed (%s): %s", reason, str(exc)[:200])
            response = _error_response(started)

        if request.action_id is not None:
            try:
                await _audit_evaluation(session, request, response, reason)
            except Exception as exc:  # noqa: BLE001 - if we cannot record it, we cannot prove it: fail closed
                reason = reason or type(exc).__name__
                logger.error("policy evaluation could not be audited (%s)", type(exc).__name__)
                if response.policy_result != PolicyResult.ERROR:
                    response = _error_response(started)

        span.set_attribute("policy.result", response.policy_result.value)
        span.set_attribute("policy.evaluated_count", response.evaluated_policy_count)
        span.set_attribute("policy.matched_count", len(response.matched_policies))
        if response.policy_result == PolicyResult.ERROR:
            span.set_status(trace.Status(trace.StatusCode.ERROR, "policy engine failure"))
        return response
