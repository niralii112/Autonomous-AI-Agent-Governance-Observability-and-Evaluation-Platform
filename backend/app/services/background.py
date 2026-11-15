"""Background jobs (spec 12.17, S1-B tasks 4 and 6): the approval sweeper and the execution reconciler.

  expire_pending_approvals(session_factory)    PENDING approvals past expires_at become EXPIRED (audited). Returns the count.
  reconcile_stale_executions(session_factory)  RUNNING executions older than 2 x EXECUTION_TIMEOUT_SECONDS become FAILED
                                               with EXECUTION_RESULT_UNRECORDED (the tool ran but nobody saved the result).

Both lock rows with SKIP LOCKED, so they never fight a reviewer or a running request, and running them from two
servers at once is safe. Both commit their own work. The loop below runs them every APPROVAL_SWEEP_INTERVAL_SECONDS
and never lets an error stop it (a database outage must not crash the server; the next round simply tries again).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import (
    ActorType, ApprovalStatus, AuditEventName, AuditOutcome, ErrorCode, ExecutionStatus,
)
from app.repositories import action_repository, approval_repository, execution_repository
from app.schemas import AuditEventCreate
from app.services.audit_service import record_audit_event

logger = logging.getLogger("governance.background")
STALE_FACTOR = 2  # spec: RUNNING rows older than 2 x EXECUTION_TIMEOUT_SECONDS


async def expire_pending_approvals(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Mark every PENDING approval that is past its expiry as EXPIRED. Returns how many were expired."""
    async with session_factory() as session:
        approvals = await approval_repository.pending_past_expiry_locked(session, datetime.now(timezone.utc))
        for approval in approvals:
            approval.approval_status = ApprovalStatus.EXPIRED.value
            await record_audit_event(session, AuditEventCreate(
                event_name=AuditEventName.APPROVAL_EXPIRED, actor_type=ActorType.SYSTEM, action_id=approval.action_id,
                entity_type="approval", entity_id=approval.approval_id, outcome=AuditOutcome.SUCCESS,
                event_data={"expires_at": approval.expires_at.isoformat(), "found_by": "sweeper"}))
        await session.commit()
        return len(approvals)


async def reconcile_stale_executions(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Close RUNNING executions that have been running for more than 2 x EXECUTION_TIMEOUT_SECONDS. Returns how many."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_FACTOR * get_settings().execution_timeout_seconds)
    async with session_factory() as session:
        stale = await execution_repository.stale_running_locked(session, cutoff)
        for execution in stale:
            execution.execution_status = ExecutionStatus.FAILED.value
            execution.error_code = ErrorCode.EXECUTION_RESULT_UNRECORDED.value
            execution.error_message = "The tool ran but its result was never recorded."
            execution.completed_at = datetime.now(timezone.utc)
            action = await action_repository.get_by_id(session, execution.action_id)
            await record_audit_event(session, AuditEventCreate(
                event_name=AuditEventName.EXECUTION_RESULT_UNRECORDED, actor_type=ActorType.SYSTEM,
                agent_id=action.agent_id if action else None, action_id=execution.action_id,
                entity_type="execution", entity_id=execution.execution_id, outcome=AuditOutcome.FAILURE,
                event_data={"attempt_number": execution.attempt_number}))
        await session.commit()
        return len(stale)


async def run_once(session_factory: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    """One round of both jobs. Returns (approvals expired, executions reconciled)."""
    return await expire_pending_approvals(session_factory), await reconcile_stale_executions(session_factory)


async def _loop(session_factory: async_sessionmaker[AsyncSession], stop: asyncio.Event, interval: float) -> None:
    while not stop.is_set():
        try:
            expired, reconciled = await run_once(session_factory)
            if expired or reconciled:
                logger.info("background round: %s approvals expired, %s executions reconciled", expired, reconciled)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed round must never stop the loop
            logger.error("background round failed (%s)", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


@dataclass
class BackgroundTasks:
    task: asyncio.Task
    stop: asyncio.Event


def start_background_tasks(session_factory: async_sessionmaker[AsyncSession], interval_seconds: float | None = None
                           ) -> BackgroundTasks:
    """Start the loop (called from the app's lifespan). interval_seconds defaults to APPROVAL_SWEEP_INTERVAL_SECONDS."""
    interval = interval_seconds if interval_seconds is not None else get_settings().approval_sweep_interval_seconds
    stop = asyncio.Event()
    return BackgroundTasks(task=asyncio.create_task(_loop(session_factory, stop, interval)), stop=stop)


async def stop_background_tasks(handle: BackgroundTasks) -> None:
    """Ask the loop to finish its round and stop; cancel it if it does not."""
    handle.stop.set()
    try:
        await asyncio.wait_for(handle.task, timeout=5)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        handle.task.cancel()
