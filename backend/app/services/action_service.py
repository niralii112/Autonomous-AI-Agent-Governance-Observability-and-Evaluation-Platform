"""submit_action: the main governance flow (spec 12.5, 13.3).

  validate -> idempotency -> TX-1 store the action
           -> facts + evaluate_policy (committed on its own)
           -> assess_risk (2 s timeout, no database connection held)
           -> TX-2 store risk, decision and approval / blocked or pending execution
           -> TX-3/4 (ALLOW only) execution_service.execute_controlled_action

submit_action commits its own transactions: this is the one place where the caller does not commit.
Security rules: mandatory policies override ML risk; agents never call tools; every failure fails closed.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from opentelemetry import trace
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.enums import (
    ActorType, AgentCategory, AgentStatus, AuditEventName, AuditOutcome, ErrorCode, ExecutionStatus,
    GovernanceDecision, PolicyResult, RiskSource, ToolSensitivity, ToolStatus, UserRole,
)
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.core.trace_context import current_trace_id
from app.models.action import Action
from app.models.execution import Execution
from app.models.governance_decision import GovernanceDecisionRow
from app.repositories import (
    action_repository, agent_repository, approval_repository, execution_repository, permission_repository,
    risk_assessment_repository, tool_repository,
)
from app.repositories import governance_decision_repository as decision_repository
from app.schemas import (
    ACTION_PAYLOAD_MODELS, ActionResponse, ActionSubmissionRequest, ActionSubmissionResponse, ActorContext,
    AuditEventCreate, ExecutionResponse, GovernanceDecisionRequest, GovernanceDecisionResponse,
    MatchedPolicy, PolicyEvaluationRequest, PolicyEvaluationResponse, RiskAssessmentRequest, RiskAssessmentResponse,
    RiskContext,
)
from app.services import approval_service, execution_service, policy_matching, policy_service
from app.services.action_views import action_response, approval_response
from app.services.audit_service import record_audit_event
from app.services.decision_service import make_governance_decision

logger = logging.getLogger("governance.action")
_tracer = trace.get_tracer("governance.action")

RISK_TIMEOUT_SECONDS = 2.0       # spec: assess_risk gets 2 seconds
IN_FLIGHT_WAIT_SECONDS = 5.0     # a duplicate request waits this long for the first one to finish
STALE_AFTER_SECONDS = 30.0       # an action with no decision after this long is resumed, not waited for


def _as_risk_response(value: Any) -> RiskAssessmentResponse:
    """assess_risk should return a RiskAssessmentResponse. A plain dict is accepted too, but only if it validates
    against the contract: anything else is not an assessment (ValidationError / TypeError are caught by the caller)."""
    if isinstance(value, RiskAssessmentResponse):
        return value
    if isinstance(value, dict):
        return RiskAssessmentResponse.model_validate(value)
    raise TypeError(f"assess_risk returned {type(value).__name__}, not a RiskAssessmentResponse")


async def _assess_risk(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """Student 2's assess_risk (spec: app.services.risk_service.assess_risk). Imported lazily so this module
    loads even before her file exists, and so tests can replace this one function."""
    from app.services.risk_service import assess_risk

    return await assess_risk(request)


# ----------------------------------------------------------------------------------------- small helpers

async def _find_tool(session: AsyncSession, request: ActionSubmissionRequest):
    """The tool the request names, or None. A tool that cannot run this kind of action counts as unknown (D-02)."""
    tool = await tool_repository.get_by_name(session, request.tool_name)
    return tool if tool is not None and tool.supported_action_type == request.action_type.value else None


def _audit(session: AsyncSession, name: AuditEventName, *, actor_type: ActorType = ActorType.SYSTEM,
           actor: ActorContext | None = None, agent_id: uuid.UUID | None = None, action_id: uuid.UUID | None = None,
           entity_type: str | None = None, entity_id: uuid.UUID | None = None,
           outcome: AuditOutcome = AuditOutcome.SUCCESS, data: dict[str, Any] | None = None):
    return record_audit_event(session, AuditEventCreate(
        event_name=name, actor_type=actor_type, actor_user_id=actor.user_id if actor else None, agent_id=agent_id,
        action_id=action_id, entity_type=entity_type, entity_id=entity_id, outcome=outcome, event_data=data or {}))


def _policy_evaluation_from_decision(decision: GovernanceDecisionRow, matched: list[MatchedPolicy]
                                     ) -> PolicyEvaluationResponse:
    """Rebuild the policy evaluation for a duplicate request from what was stored. The values that are not
    stored (latency and the number of evaluated policies) are approximated."""
    result = PolicyResult(decision.policy_result)
    chosen, winner = policy_matching.choose_winner(matched) if result != PolicyResult.ERROR else (PolicyResult.ERROR, None)
    return PolicyEvaluationResponse(
        policy_result=result, matched_policies=matched, winning_policy_id=winner.policy_id if winner else None,
        conflict_detected=policy_matching.conflict_detected(matched), evaluated_policy_count=len(matched),
        policy_snapshot_hash=decision.policy_snapshot_hash,
        error_code=ErrorCode.POLICY_ENGINE_FAILURE if result == PolicyResult.ERROR else None, latency_ms=0.0)


async def _matched_policies(session: AsyncSession, decision: GovernanceDecisionRow) -> list[MatchedPolicy]:
    from sqlalchemy import select

    from app.models.policy import Policy

    ids = [uuid.UUID(str(i)) for i in decision.matched_policy_ids]
    if not ids:
        return []
    rows = (await session.execute(select(Policy).where(Policy.policy_id.in_(ids)))).scalars()
    return sorted((MatchedPolicy(policy_id=p.policy_id, policy_key=p.policy_key, version=p.version, effect=p.effect,
                                 priority=p.priority, is_mandatory=p.is_mandatory) for p in rows),
                  key=lambda m: (m.priority, m.policy_key))


async def _assemble(session: AsyncSession, action: Action, decision: GovernanceDecisionRow,
                    policy_evaluation: PolicyEvaluationResponse | None, duplicate: bool) -> ActionSubmissionResponse:
    """The ActionSubmissionResponse for the current state of an action, read back from the database."""
    if policy_evaluation is None:
        policy_evaluation = _policy_evaluation_from_decision(decision, await _matched_policies(session, decision))
    risk = (await risk_assessment_repository.get_by_id(session, decision.risk_assessment_id)
            if decision.risk_assessment_id else None)
    approval = await approval_repository.for_decision(session, decision.governance_decision_id)
    execution = await execution_repository.latest_for_action(session, action.action_id)
    return ActionSubmissionResponse(
        action=action_response(action), policy_evaluation=policy_evaluation,
        risk_assessment=RiskAssessmentResponse.model_validate(risk) if risk else None,
        governance_decision=GovernanceDecisionResponse.model_validate(decision),
        approval=await approval_response(session, approval) if approval else None,
        execution=ExecutionResponse.model_validate(execution) if execution else None, duplicate=duplicate)


async def _wait_for_decision(session: AsyncSession, action: Action) -> GovernanceDecisionRow | None:
    """Another request is processing the same action: wait briefly for its decision."""
    deadline = asyncio.get_running_loop().time() + IN_FLIGHT_WAIT_SECONDS
    while True:
        await session.commit()  # end the transaction so the next read sees fresh data
        decision = await decision_repository.latest_for_action(session, action.action_id)
        if decision is not None or asyncio.get_running_loop().time() >= deadline:
            return decision
        await asyncio.sleep(0.1)


# ----------------------------------------------------------------------------------------------- main flow

async def submit_action(session: AsyncSession, request: ActionSubmissionRequest, actor: ActorContext
                        ) -> ActionSubmissionResponse:
    if actor.role not in (UserRole.ADMIN, UserRole.OPERATOR):
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")
    settings = get_settings()

    with _tracer.start_as_current_span("action.submit") as span:
        span.set_attribute("agent.id", str(request.agent_id))
        span.set_attribute("action.type", request.action_type.value)

        # ---- 1. the agent must exist, and the payload must have the right shape
        agent = await agent_repository.get_by_id(session, request.agent_id)
        if agent is None:
            await _audit(session, AuditEventName.ACTION_REJECTED_PRE_VALIDATION, actor_type=ActorType.USER, actor=actor,
                         outcome=AuditOutcome.DENIED, data={"reason": "agent_not_registered", "agent_id": str(request.agent_id)})
            await session.commit()
            raise AppError(ErrorCode.AGENT_NOT_REGISTERED, "No registered agent has this agent_id.")
        try:
            ACTION_PAYLOAD_MODELS[request.action_type].model_validate(request.action_payload)
        except ValidationError as exc:
            problems = {".".join(str(p) for p in e["loc"]) or "action_payload": e["msg"] for e in exc.errors()}
            await _audit(session, AuditEventName.ACTION_REJECTED_PRE_VALIDATION, actor_type=ActorType.USER, actor=actor,
                         agent_id=agent.agent_id, outcome=AuditOutcome.DENIED,
                         data={"reason": "invalid_action_payload", "fields": sorted(problems)})
            await session.commit()
            raise AppError(ErrorCode.INVALID_ACTION_PAYLOAD,
                           "action_payload does not match the schema for this action_type.", problems) from None

        payload_hash = compute_payload_hash(request.action_payload)
        tool = await _find_tool(session, request)

        # ---- 2. idempotency: the same agent + key never creates a second action
        action = await action_repository.get_by_agent_and_key(session, agent.agent_id, request.idempotency_key)
        if action is not None:
            action = await _existing_action(session, action, payload_hash, actor)
            if isinstance(action, ActionSubmissionResponse):
                return action

        # ---- 3. TX-1: store the action
        if action is None:
            action = Action(
                agent_id=agent.agent_id, tool_id=tool.tool_id if tool else None, requested_tool_name=request.tool_name,
                action_type=request.action_type.value, action_payload=request.action_payload, payload_hash=payload_hash,
                idempotency_key=request.idempotency_key, submitted_by_user_id=actor.user_id, trace_id=current_trace_id())
            session.add(action)
            try:
                await session.flush()
            except IntegrityError:  # another request with the same key got there first
                await session.rollback()
                session.expunge_all()  # a rollback expires everything we hold: reload what we still need
                agent = await agent_repository.get_by_id(session, request.agent_id)
                tool = await _find_tool(session, request)
                other = await action_repository.get_by_agent_and_key(session, agent.agent_id, request.idempotency_key)
                if other is None:
                    raise
                result = await _existing_action(session, other, payload_hash, actor, racing=True)
                if isinstance(result, ActionSubmissionResponse):
                    return result
                action = result
            else:
                await _audit(session, AuditEventName.ACTION_SUBMITTED, actor_type=ActorType.USER, actor=actor,
                             agent_id=agent.agent_id, action_id=action.action_id, entity_type="action",
                             entity_id=action.action_id, data={"action_type": action.action_type, "tool_name": request.tool_name})
                await session.commit()
        span.set_attribute("action.id", str(action.action_id))

        # ---- 4. the facts the decision needs, then the policy engine (committed on its own)
        permission = await permission_repository.get_for_agent_tool(session, agent.agent_id, tool.tool_id) if tool else None
        permitted = permission is not None and permission.is_allowed
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        blocked_24h = await decision_repository.count_blocked_since(session, agent.agent_id, since, action.action_id)
        failed_24h = await execution_repository.count_failed_since(session, agent.agent_id, since, action.action_id)
        agent_category = AgentCategory(agent.agent_category)
        sensitivity = ToolSensitivity(tool.tool_sensitivity) if tool else None

        policy_evaluation = await policy_service.evaluate_policy(session, PolicyEvaluationRequest(
            action_id=action.action_id, agent_id=agent.agent_id, agent_category=agent_category,
            action_type=request.action_type, tool_name=request.tool_name, tool_sensitivity=sensitivity,
            action_payload=request.action_payload))
        await session.commit()  # releases the connection before the risk model runs

        # ---- 5. risk (Student 2). Any failure means "no risk assessment", and the decision engine reviews it.
        risk, risk_problem = None, None
        if tool is not None:
            try:
                risk = await asyncio.wait_for(_assess_risk(RiskAssessmentRequest(
                    action_id=action.action_id, agent_id=agent.agent_id, agent_category=agent_category,
                    action_type=request.action_type, tool_name=request.tool_name, tool_sensitivity=sensitivity,
                    action_payload=request.action_payload,
                    context=RiskContext(recent_blocked_count_24h=blocked_24h, recent_failed_count_24h=failed_24h,
                                        agent_trust_tier=agent.trust_tier, submitted_at=action.created_at))),
                    timeout=RISK_TIMEOUT_SECONDS)
                risk = _as_risk_response(risk)
                if risk.action_id != action.action_id:  # an answer about some other action is not usable
                    risk, risk_problem = None, "risk_response_for_another_action"
            except asyncio.TimeoutError:
                risk, risk_problem = None, "risk_timeout"
            except (ValidationError, TypeError) as exc:  # an answer that is not a valid assessment is not used
                logger.error("assess_risk returned something unusable (%s)", type(exc).__name__)
                risk, risk_problem = None, "risk_response_invalid"
            except Exception as exc:  # noqa: BLE001 - spec: try/except around assess_risk, fail closed
                logger.error("assess_risk failed (%s)", type(exc).__name__)
                risk, risk_problem = None, f"risk_error_{type(exc).__name__}"

        # ---- 6. TX-2: store risk and decision, then approval / blocked or pending execution
        auto_registered = False
        if risk is not None:
            try:
                async with session.begin_nested():  # a problem storing the risk must not lose the whole decision
                    auto_registered = await risk_assessment_repository.ensure_model_version(session, risk)
                    await risk_assessment_repository.add(session, risk)
            except Exception as exc:  # noqa: BLE001
                logger.error("risk assessment could not be stored (%s)", type(exc).__name__)
                risk, risk_problem = None, "risk_not_storable"

        if risk is not None:
            await _audit(session, AuditEventName.RISK_FALLBACK_USED if risk.risk_source == RiskSource.HEURISTIC_FALLBACK
                         else AuditEventName.RISK_ASSESSED, agent_id=agent.agent_id, action_id=action.action_id,
                         entity_type="risk_assessment", entity_id=risk.risk_assessment_id,
                         data={"risk_level": risk.risk_level.value, "risk_source": risk.risk_source.value,
                               "model_version": risk.model_version, "model_auto_registered": auto_registered})
        else:
            await _audit(session, AuditEventName.RISK_ASSESSED, agent_id=agent.agent_id, action_id=action.action_id,
                         outcome=AuditOutcome.FAILURE, data={"reason": risk_problem or "no_tool_to_assess"})

        outcome = make_governance_decision(GovernanceDecisionRequest(
            action_id=str(action.action_id), agent_status=AgentStatus(agent.agent_status), tool_found=tool is not None,
            tool_status=ToolStatus(tool.tool_status) if tool else None, agent_tool_permitted=permitted,
            tool_sensitivity=sensitivity, policy_evaluation=policy_evaluation, risk_assessment=risk,
            no_match_decision=settings.governance_no_match_decision))

        decision = GovernanceDecisionRow(
            action_id=action.action_id, decision_sequence=1, policy_result=policy_evaluation.policy_result.value,
            final_decision=outcome.final_decision.value, decision_reason_code=outcome.decision_reason_code,
            decision_rule_id=outcome.decision_rule_id, risk_assessment_id=risk.risk_assessment_id if risk else None,
            matched_policy_ids=[str(m.policy_id) for m in policy_evaluation.matched_policies],
            policy_snapshot_hash=policy_evaluation.policy_snapshot_hash, payload_hash=payload_hash)
        session.add(decision)
        await session.flush()
        await session.refresh(decision)
        await _audit(session, AuditEventName.GOVERNANCE_DECISION_MADE, agent_id=agent.agent_id, action_id=action.action_id,
                     entity_type="governance_decision", entity_id=decision.governance_decision_id,
                     data={"final_decision": outcome.final_decision.value, "rule": outcome.decision_rule_id,
                           "reason": outcome.decision_reason_code, "policy_result": decision.policy_result})
        span.set_attribute("decision.final", outcome.final_decision.value)
        span.set_attribute("decision.rule", outcome.decision_rule_id)

        execution_id: uuid.UUID | None = None
        if outcome.final_decision == GovernanceDecision.HUMAN_REVIEW:
            await approval_service.request_human_approval(
                session, action_id=action.action_id, agent_id=agent.agent_id,
                governance_decision_id=decision.governance_decision_id, payload_hash=payload_hash)
        else:
            blocked = outcome.final_decision == GovernanceDecision.BLOCK
            execution = Execution(
                action_id=action.action_id, governance_decision_id=decision.governance_decision_id, attempt_number=1,
                execution_status=(ExecutionStatus.BLOCKED if blocked else ExecutionStatus.PENDING).value,
                completed_at=datetime.now(timezone.utc) if blocked else None, trace_id=current_trace_id(),
                error_message=f"Blocked by rule {outcome.decision_rule_id}: {outcome.decision_reason_code}" if blocked else None)
            session.add(execution)
            await session.flush()
            execution_id = execution.execution_id
            if blocked:
                await _audit(session, AuditEventName.EXECUTION_BLOCKED, agent_id=agent.agent_id, action_id=action.action_id,
                             entity_type="execution", entity_id=execution.execution_id, outcome=AuditOutcome.DENIED,
                             data={"rule": outcome.decision_rule_id, "reason": outcome.decision_reason_code})
        await session.commit()

        # ---- 7. TX-3 and TX-4: only an ALLOW decision is executed, and only through execution_service
        if outcome.final_decision == GovernanceDecision.ALLOW and execution_id is not None:
            factory = async_sessionmaker(session.bind, expire_on_commit=False) if session.bind is not None \
                else get_session_factory()
            await execution_service.execute_controlled_action(factory, execution_id)
            await session.commit()

        decision_id, action_id = decision.governance_decision_id, action.action_id
        session.expunge_all()  # the execution changed in another session: forget cached rows and read fresh ones
        action = await action_repository.get_by_id(session, action_id)
        decision = await decision_repository.get_by_id(session, decision_id)
        response = await _assemble(session, action, decision, policy_evaluation, duplicate=False)
        await session.commit()
        return response


async def _existing_action(session: AsyncSession, action: Action, payload_hash: str, actor: ActorContext,
                           racing: bool = False) -> "Action | ActionSubmissionResponse":
    """The same agent and key were used before. Same payload: return the original outcome (duplicate=true).
    Different payload: 409. An action that never got a decision (a crash, or still being processed) is waited
    for briefly and, if it is stale, resumed."""
    if action.payload_hash != payload_hash:
        raise AppError(ErrorCode.IDEMPOTENCY_KEY_CONFLICT, "This idempotency_key was already used with a different payload.")
    decision = await decision_repository.latest_for_action(session, action.action_id)
    if decision is None:
        age = (datetime.now(timezone.utc) - action.created_at).total_seconds()
        if racing or age < STALE_AFTER_SECONDS:
            decision = await _wait_for_decision(session, action)
        if decision is None:
            if age >= STALE_AFTER_SECONDS:
                return action  # stale: resume the flow for this same action
            raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "This action is still being processed. Retry shortly.")
    await _audit(session, AuditEventName.ACTION_DUPLICATE_DETECTED, actor_type=ActorType.USER, actor=actor,
                 agent_id=action.agent_id, action_id=action.action_id, entity_type="action", entity_id=action.action_id)
    response = await _assemble(session, action, decision, None, duplicate=True)
    await session.commit()
    return response
