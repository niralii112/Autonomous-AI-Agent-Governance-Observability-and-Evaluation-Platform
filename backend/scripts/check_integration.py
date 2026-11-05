"""Checks that Student 2's real modules fit the interfaces that submit_action and execution_service use.

Run from the backend folder:   python scripts/check_integration.py

It calls her real risk model and her real tool registry, the same way the governance code does, and
prints PASS or FAIL for each check with a hint. It changes nothing in the database.
"""

import asyncio
import inspect
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.enums import ActionType, AgentCategory, ToolSensitivity  # noqa: E402
from app.core.execution_grant import mint_execution_grant  # noqa: E402
from app.core.hashing import compute_payload_hash  # noqa: E402
from app.schemas import (  # noqa: E402
    RiskAssessmentRequest, RiskAssessmentResponse, RiskContext, ToolInvocationRequest, ToolInvocationResult,
)

SEED_MODEL_VERSIONS = {"heuristic-v1", "risk-logreg-1.0.0"}
SEED_TOOLS = {  # tool_name: (action_type, a payload that satisfies the contract)
    "finance_report_reader": ("FINANCE_GET_REPORT", {"report_id": "rpt-001", "period": "2026-Q3"}),
    "finance_summary_generator": ("FINANCE_GENERATE_SUMMARY", None),
    "payment_processor_sim": ("FINANCE_PROPOSE_PAYMENT", {"payee_id": "payee-0001", "amount": 450, "currency": "USD", "reference": "inv-1"}),
    "finance_records_vault": ("FINANCE_ACCESS_SENSITIVE_RECORDS", {"record_set": "payroll", "record_count": 3, "justification": "audit"}),
    "ticket_reader": ("SUPPORT_GET_TICKET", None),
    "support_response_generator": ("SUPPORT_GENERATE_RESPONSE", None),
    "refund_processor_sim": ("SUPPORT_PROPOSE_REFUND", None),
    "customer_info_accessor": ("SUPPORT_ACCESS_CUSTOMER_INFO", None),
}
results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, hint: str = "") -> bool:
    results.append((ok, name, hint))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        -> {hint}" if hint and not ok else ""))
    return ok


async def check_risk_service() -> None:
    print("\nRisk service (app.services.risk_service.assess_risk)")
    try:
        from app.services import risk_service
    except ImportError as exc:
        check(False, "module app.services.risk_service can be imported", f"{exc}")
        return
    fn = getattr(risk_service, "assess_risk", None)
    if not check(fn is not None and inspect.iscoroutinefunction(fn), "assess_risk exists and is `async def`",
                 "spec: async def assess_risk(request: RiskAssessmentRequest) -> RiskAssessmentResponse"):
        return
    params = list(inspect.signature(fn).parameters)
    check(len(params) == 1, "assess_risk takes exactly one argument (the request)", f"it takes {params}")

    action_id = uuid.uuid4()
    request = RiskAssessmentRequest(
        action_id=action_id, agent_id=uuid.uuid4(), agent_category=AgentCategory.FINANCE,
        action_type=ActionType.FINANCE_PROPOSE_PAYMENT, tool_name="payment_processor_sim",
        tool_sensitivity=ToolSensitivity.WRITE, action_payload=SEED_TOOLS["payment_processor_sim"][1],
        context=RiskContext(recent_blocked_count_24h=0, recent_failed_count_24h=0, agent_trust_tier=2,
                            submitted_at=datetime.now(timezone.utc)))
    try:
        started = asyncio.get_running_loop().time()
        response = await asyncio.wait_for(fn(request), timeout=2.0)
        elapsed = (asyncio.get_running_loop().time() - started) * 1000
    except asyncio.TimeoutError:
        check(False, "assess_risk answers within the 2 second limit", "it took longer than 2 s")
        return
    except Exception as exc:  # noqa: BLE001
        check(False, "assess_risk runs on a normal request", f"{type(exc).__name__}: {str(exc)[:120]}")
        return
    check(True, f"assess_risk answers a normal request ({elapsed:.0f} ms)")
    if isinstance(response, RiskAssessmentResponse):
        check(True, "it returns a RiskAssessmentResponse")
    elif isinstance(response, dict):
        try:
            response = RiskAssessmentResponse.model_validate(response)
            check(True, "it returns a dict that validates as a RiskAssessmentResponse (accepted; the spec asks for the model itself)")
        except Exception as exc:  # noqa: BLE001
            check(False, "the dict it returns validates as a RiskAssessmentResponse", f"{str(exc)[:200]}")
    else:
        check(False, "it returns a RiskAssessmentResponse", f"it returned {type(response).__name__}")
    if isinstance(response, RiskAssessmentResponse):
        check(response.action_id == action_id, "the response carries the SAME action_id as the request",
              "submit_action discards an answer about another action")
        check(response.model_version in SEED_MODEL_VERSIONS, f"model_version {response.model_version!r} is a seeded one",
              f"seeded: {sorted(SEED_MODEL_VERSIONS)}. An unknown name still works: it is registered inactive and logged")
        check(response.risk_source.value in ("ML_MODEL", "HEURISTIC_FALLBACK"), f"risk_source is {response.risk_source.value}")


async def check_tools() -> None:
    print("\nTool registry (app.tools.registry.get_tool_implementation)")
    try:
        from app.tools.registry import get_tool_implementation
    except ImportError as exc:
        check(False, "module app.tools.registry can be imported", f"{exc}. Spec: get_tool_implementation(tool_name) lives there")
        return
    check(callable(get_tool_implementation), "get_tool_implementation exists")
    check(get_tool_implementation("no_such_tool_xyz") is None, "an unknown tool name returns None (not an error)")
    for name, (action_type, payload) in SEED_TOOLS.items():
        tool = get_tool_implementation(name)
        if not check(tool is not None, f"a tool is registered for {name}", "execution would end FAILED / TOOL_NOT_AVAILABLE"):
            continue
        invoke = getattr(tool, "invoke", None)
        if not check(invoke is not None and inspect.iscoroutinefunction(invoke), f"  {name}.invoke is `async def`",
                     "spec: async def invoke(invocation, grant) -> ToolInvocationResult"):
            continue
        if payload is None:
            continue  # only the tools with a ready-made payload are called
        invocation = ToolInvocationRequest(execution_id=uuid.uuid4(), action_id=uuid.uuid4(), tool_name=name,
                                           action_type=ActionType(action_type), action_payload=payload)
        grant = mint_execution_grant(invocation.execution_id, invocation.action_id, name, compute_payload_hash(payload))
        try:
            result = await asyncio.wait_for(invoke(invocation, grant), timeout=5.0)
            check(isinstance(result, ToolInvocationResult), f"  {name}.invoke returns a ToolInvocationResult with a valid grant",
                  f"it returned {type(result).__name__}")
        except Exception as exc:  # noqa: BLE001
            check(False, f"  {name}.invoke works with a valid grant", f"{type(exc).__name__}: {str(exc)[:120]}")
        # the same grant a second time must be refused (single use)
        try:
            await asyncio.wait_for(invoke(invocation, grant), timeout=5.0)
            check(False, f"  {name} refuses a grant that was already used", "the tool ran twice with one grant")
        except Exception:  # noqa: BLE001 - any refusal is what we want
            check(True, f"  {name} refuses a grant that was already used")
        try:
            await asyncio.wait_for(invoke(invocation, None), timeout=5.0)
            check(False, f"  {name} refuses to run without a grant", "a tool must fail closed without a grant")
        except Exception:  # noqa: BLE001
            check(True, f"  {name} refuses to run without a grant")


async def main() -> int:
    get_settings()  # fails early, with a clear message, if .env is incomplete
    print("Checking Student 2's modules against the interfaces used by submit_action and execution_service")
    await check_risk_service()
    await check_tools()
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
