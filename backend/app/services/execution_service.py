"""Controlled execution (spec 12.7, 13.6): the ONLY place that mints grants and runs tools.

execute_controlled_action works in short transactions and never holds a database connection while
a tool runs:

  TX-3  lock the execution row, REVALIDATE everything, consume the approval and set RUNNING   (commit)
        mint a grant, run the tool with a timeout                                            (no transaction)
  TX-4  record_execution_result: SUCCEEDED or FAILED, with an audit event                     (commit)

If anything in the revalidation fails, the execution becomes BLOCKED with POLICY_REVALIDATION_FAILED
and the tool is never called. Nothing here raises for tool problems: they become FAILED rows.
"""

import asyncio
import inspect
import logging
import uuid
from functools import lru_cache
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import (
    ActionType, ActorType, AgentCategory, AgentStatus, ApprovalStatus, AuditEventName, AuditOutcome, ErrorCode,
    ExecutionStatus, PolicyResult, ToolSensitivity, ToolStatus,
)
from app.core.exceptions import AppError, NotFoundError
from app.core.execution_grant import mint_execution_grant, verify_execution_grant
from app.core.hashing import compute_payload_hash
from app.models.execution import Execution
from app.repositories import (
    action_repository, agent_repository, approval_repository, execution_repository, permission_repository,
    tool_repository,
)
from app.repositories import governance_decision_repository as decision_repository
from app.schemas import (
    AuditEventCreate, ExecutionOutcome, ExecutionResponse, PolicyEvaluationRequest, ToolInvocationRequest,
    ToolInvocationResult,
)
from app.services import policy_service
from app.services.audit_service import record_audit_event

logger = logging.getLogger("governance.execution")
_tracer = trace.get_tracer("governance.execution")


def _grant_verifier(grant: Any, invocation: Any) -> bool:
    """The verifier handed to every tool. It is the real check: signature, expiry, this exact call, an unchanged
    payload, and single use. verify_execution_grant raises when anything is wrong, and the tool turns that
    into a refusal. Tools never mint or verify grants on their own."""
    verify_execution_grant(grant, invocation)
    return True


@lru_cache(maxsize=1)
def _tool_registry() -> dict[str, Any]:
    """Student 2's registry (app.tools.build_tool_registry), built once with our verifier."""
    from app.tools import build_tool_registry

    return build_tool_registry(_grant_verifier)


def get_tool_implementation(tool_name: str) -> Any | None:
    """Find the code for a tool. This is the ONLY place that imports Student 2's tools, so only
    execution_service can reach them. Returns None when nothing is registered under that name.

    Lookup order: app.tools.registry.get_tool_implementation (the spec's location), then
    app.tools.build_tool_registry (what Student 2 has built)."""
    try:
        from app.tools.registry import get_tool_implementation as spec_lookup
    except ImportError:
        pass
    else:
        return spec_lookup(tool_name)
    try:
        return _tool_registry().get(tool_name)
    except ImportError:
        logger.error("the tool package could not be imported")
        return None


def _error_code_of(value: Any) -> ErrorCode | None:
    if isinstance(value, ErrorCode):
        return value
    try:
        return ErrorCode(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _normalize_tool_result(raw: Any) -> ToolInvocationResult:
    """Accept what tools actually return: a ToolInvocationResult, or a dict such as
    {"success": True, "output": {...}} or {"success": False, "error_code": ..., "error_message": ...}.
    Anything else is not a result (TypeError, which becomes a FAILED execution)."""
    if isinstance(raw, ToolInvocationResult):
        return raw
    if isinstance(raw, dict) and raw.get("success") is True:
        output = raw.get("output", {})
        return ToolInvocationResult(success=True, output=output if isinstance(output, dict) else {"output": output},
                                    error_code=None, error_message=None)
    if isinstance(raw, dict) and raw.get("success") is False:
        return ToolInvocationResult(
            success=False, output={}, error_code=_error_code_of(raw.get("error_code")) or ErrorCode.TOOL_EXECUTION_FAILED,
            error_message=str(raw.get("error_message") or raw.get("message") or "The tool reported a failure.")[:500])
    raise TypeError(f"a tool returned {type(raw).__name__}, which is not a result")


async def _call_tool(tool: Any, invocation: ToolInvocationRequest, grant: Any, timeout: float) -> ToolInvocationResult:
    """Run a tool with a time limit. Works for both `async def invoke` and a plain `def invoke`; a plain one runs in
    a worker thread so a slow tool cannot freeze the server. A tool that raises an error carrying an ErrorCode
    (like Student 2's ToolInvocationError) becomes a failed result with that code; any other exception propagates."""
    try:
        if inspect.iscoroutinefunction(tool.invoke):
            raw = await asyncio.wait_for(tool.invoke(invocation, grant), timeout=timeout)
        else:
            raw = await asyncio.wait_for(asyncio.to_thread(tool.invoke, invocation, grant), timeout=timeout)
            if inspect.isawaitable(raw):
                raw = await raw
    except asyncio.TimeoutError:
        raise
    except Exception as exc:  # noqa: BLE001
        code = _error_code_of(getattr(exc, "error_code", None))
        if code is None:
            raise
        return ToolInvocationResult(success=False, output={}, error_code=code, error_message=str(exc)[:500])
    return _normalize_tool_result(raw)


async def _audit(session: AsyncSession, event: AuditEventName, execution: Execution, agent_id: uuid.UUID | None,
                 outcome: AuditOutcome, data: dict[str, Any]) -> None:
    await record_audit_event(session, AuditEventCreate(
        event_name=event, actor_type=ActorType.SYSTEM, agent_id=agent_id, action_id=execution.action_id,
        entity_type="execution", entity_id=execution.execution_id, outcome=outcome, event_data=data))


def _block(execution: Execution, error_code: ErrorCode, message: str) -> None:
    """Mark an execution BLOCKED. It never started, so started_at stays empty."""
    execution.execution_status = ExecutionStatus.BLOCKED.value
    execution.error_code = error_code.value
    execution.error_message = message
    execution.completed_at = datetime.now(timezone.utc)


async def _revalidate(session: AsyncSession, execution: Execution) -> tuple[ErrorCode, str] | None:
    """Spec 13.6. Returns (error_code, reason) for the first problem found, or None when all is well."""
    action = await action_repository.get_by_id(session, execution.action_id)
    if action is None:
        return ErrorCode.POLICY_REVALIDATION_FAILED, "action_missing"
    # 1. the payload must still be exactly what was evaluated and approved
    try:
        current_hash = compute_payload_hash(action.action_payload)
    except (TypeError, ValueError):
        return ErrorCode.POLICY_REVALIDATION_FAILED, "payload_unhashable"
    decision = await decision_repository.get_by_id(session, execution.governance_decision_id)
    if decision is None or not (current_hash == action.payload_hash == decision.payload_hash):
        return ErrorCode.POLICY_REVALIDATION_FAILED, "payload_changed"

    # 2. agent, tool and permission must still be in order
    agent = await agent_repository.get_by_id(session, action.agent_id)
    if agent is None or agent.agent_status != AgentStatus.ACTIVE.value:
        return ErrorCode.POLICY_REVALIDATION_FAILED, "agent_not_active"
    tool = await tool_repository.get_by_id(session, action.tool_id) if action.tool_id else None
    if tool is None or tool.tool_status != ToolStatus.ACTIVE.value:
        return ErrorCode.POLICY_REVALIDATION_FAILED, "tool_not_active"
    permission = await permission_repository.get_for_agent_tool(session, agent.agent_id, tool.tool_id)
    if permission is None or not permission.is_allowed:
        return ErrorCode.POLICY_REVALIDATION_FAILED, "permission_revoked"

    # 3. a fresh policy evaluation must not say BLOCK or ERROR (a different but non-blocking result is only drift)
    fresh = await policy_service.evaluate_policy(session, PolicyEvaluationRequest(
        action_id=None, agent_id=agent.agent_id, agent_category=AgentCategory(agent.agent_category),
        action_type=ActionType(action.action_type), tool_name=tool.tool_name,
        tool_sensitivity=ToolSensitivity(tool.tool_sensitivity), action_payload=action.action_payload))
    if fresh.policy_result in (PolicyResult.BLOCK, PolicyResult.ERROR):
        return ErrorCode.POLICY_REVALIDATION_FAILED, f"fresh_policy_{fresh.policy_result.value.lower()}"
    if fresh.policy_snapshot_hash != decision.policy_snapshot_hash:
        logger.info("policy drift for action %s: snapshot hash changed since the decision", action.action_id)

    # 4. an approval, if there is one, must be APPROVED, unexpired and unused
    if execution.approval_id is not None:
        approval = await approval_repository.get_locked(session, execution.approval_id)
        if approval is None or approval.approval_status != ApprovalStatus.APPROVED.value:
            return ErrorCode.POLICY_REVALIDATION_FAILED, "approval_not_approved"
        if approval.consumed_at is not None:
            return ErrorCode.APPROVAL_ALREADY_CONSUMED, "approval_already_consumed"
        if approval.expires_at <= datetime.now(timezone.utc):
            return ErrorCode.POLICY_REVALIDATION_FAILED, "approval_expired"
    return None


async def execute_controlled_action(
    session_factory: async_sessionmaker[AsyncSession], execution_id: uuid.UUID
) -> ExecutionResponse:
    settings = get_settings()
    with _tracer.start_as_current_span("execution.run") as span:
        # ------------------------------------------------ TX-3: revalidate, consume approval, RUNNING
        async with session_factory() as session:
            execution = await execution_repository.get_locked(session, execution_id)
            if execution is None:
                raise NotFoundError("Execution not found.")
            if execution.execution_status != ExecutionStatus.PENDING.value:
                raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "Only a PENDING execution can be executed.",
                               {"execution_status": execution.execution_status})
            action = await action_repository.get_by_id(session, execution.action_id)
            agent_id = action.agent_id if action else None

            problem = await _revalidate(session, execution)
            if problem is not None:
                code, reason = problem
                _block(execution, code, f"Revalidation failed: {reason}")
                await _audit(session, AuditEventName.EXECUTION_REVALIDATION_FAILED, execution, agent_id,
                             AuditOutcome.DENIED, {"reason": reason, "error_code": code.value})
                await session.commit()
                await session.refresh(execution)  # updated_at is set by the database
                span.set_attribute("execution.status", "BLOCKED")
                return ExecutionResponse.model_validate(execution)

            action_tool_name = (await tool_repository.get_by_id(session, action.tool_id)).tool_name
            tool_impl = get_tool_implementation(action_tool_name)
            if tool_impl is None:  # nothing was consumed yet, so the approval stays usable
                execution.execution_status = ExecutionStatus.FAILED.value
                execution.error_code = ErrorCode.TOOL_NOT_AVAILABLE.value
                execution.error_message = "No implementation is registered for this tool."
                execution.completed_at = datetime.now(timezone.utc)
                await _audit(session, AuditEventName.EXECUTION_FAILED, execution, agent_id, AuditOutcome.FAILURE,
                             {"error_code": ErrorCode.TOOL_NOT_AVAILABLE.value, "tool_name": action_tool_name})
                await session.commit()
                await session.refresh(execution)
                return ExecutionResponse.model_validate(execution)

            now = datetime.now(timezone.utc)
            if execution.approval_id is not None:  # consumed in the SAME transaction that sets RUNNING
                (await approval_repository.get_locked(session, execution.approval_id)).consumed_at = now
            execution.execution_status = ExecutionStatus.RUNNING.value
            execution.started_at = now
            await _audit(session, AuditEventName.EXECUTION_STARTED, execution, agent_id, AuditOutcome.SUCCESS,
                         {"attempt_number": execution.attempt_number, "tool_name": action_tool_name})
            invocation = ToolInvocationRequest(
                execution_id=execution.execution_id, action_id=action.action_id, tool_name=action_tool_name,
                action_type=ActionType(action.action_type), action_payload=action.action_payload)
            grant_inputs = (execution.execution_id, action.action_id, action_tool_name, action.payload_hash)
            await session.commit()

        # ------------------------------------------------ the tool runs here: no database connection is held
        started = perf_counter()
        outcome_status, error_code, error_message, output = ExecutionStatus.SUCCEEDED, None, None, None
        try:
            grant = mint_execution_grant(*grant_inputs)
            result = await _call_tool(tool_impl, invocation, grant, settings.execution_timeout_seconds)
            if result.success:
                output = result.output
            else:
                outcome_status = ExecutionStatus.FAILED
                error_code = result.error_code or ErrorCode.TOOL_EXECUTION_FAILED
                error_message = (result.error_message or "The tool reported a failure.")[:500]
        except asyncio.TimeoutError:
            outcome_status, error_code = ExecutionStatus.FAILED, ErrorCode.TOOL_EXECUTION_TIMEOUT
            error_message = f"The tool did not finish within {settings.execution_timeout_seconds} seconds."
        except Exception as exc:  # noqa: BLE001 - a crashing tool must become a FAILED row, never a crash here
            logger.error("tool %s raised %s", grant_inputs[2], type(exc).__name__)
            outcome_status, error_code = ExecutionStatus.FAILED, ErrorCode.TOOL_EXECUTION_FAILED
            error_message = f"The tool raised an error ({type(exc).__name__})."
        latency_ms = round((perf_counter() - started) * 1000, 3)

        # ------------------------------------------------ TX-4: record the result
        async with session_factory() as session:
            response = await record_execution_result(session, execution_id, ExecutionOutcome(
                execution_status=outcome_status, result_summary=output, error_code=error_code,
                error_message=error_message, latency_ms=latency_ms))
            await session.commit()
        span.set_attribute("execution.status", response.execution_status.value)
        return response


async def record_execution_result(session: AsyncSession, execution_id: uuid.UUID, outcome: ExecutionOutcome
                                  ) -> ExecutionResponse:
    """Store the final result of a RUNNING execution (SUCCEEDED or FAILED). The caller commits."""
    if outcome.execution_status not in (ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED):
        raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "A result must be SUCCEEDED or FAILED.")
    execution = await execution_repository.get_locked(session, execution_id)
    if execution is None:
        raise NotFoundError("Execution not found.")
    if execution.execution_status != ExecutionStatus.RUNNING.value:
        raise AppError(ErrorCode.INVALID_STATE_TRANSITION, "Only a RUNNING execution can receive a result.",
                       {"execution_status": execution.execution_status})
    execution.execution_status = outcome.execution_status.value
    execution.completed_at = datetime.now(timezone.utc)
    execution.result_summary = outcome.result_summary
    execution.error_code = outcome.error_code.value if outcome.error_code else None
    execution.error_message = outcome.error_message
    execution.latency_ms = outcome.latency_ms
    await session.flush()
    action = await action_repository.get_by_id(session, execution.action_id)
    succeeded = outcome.execution_status == ExecutionStatus.SUCCEEDED
    await _audit(session, AuditEventName.EXECUTION_SUCCEEDED if succeeded else AuditEventName.EXECUTION_FAILED,
                 execution, action.agent_id if action else None,
                 AuditOutcome.SUCCESS if succeeded else AuditOutcome.FAILURE,
                 {"latency_ms": float(outcome.latency_ms), "error_code": outcome.error_code.value if outcome.error_code else None})
    await session.refresh(execution)
    return ExecutionResponse.model_validate(execution)
