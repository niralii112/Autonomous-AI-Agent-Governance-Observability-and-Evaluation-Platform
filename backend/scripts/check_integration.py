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
CATALOG = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "scenarios" / "scenario-catalog.json"
SEED_TOOL_NAMES = ["finance_report_reader", "finance_summary_generator", "payment_processor_sim", "finance_records_vault",
                   "ticket_reader", "support_response_generator", "refund_processor_sim", "customer_info_accessor"]


def sample_calls() -> dict[str, tuple[str, dict]]:
    """tool_name -> (action_type, a payload that satisfies the contract), taken from the scenario catalog."""
    import json

    data = json.loads(CATALOG.read_text())
    out: dict[str, tuple[str, dict]] = {}
    for item in (data["scenarios"] if isinstance(data, dict) else data):
        out.setdefault(item["tool_name"], (item["action_type"], item["action_payload"]))
    return out


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
        tool_sensitivity=ToolSensitivity.WRITE, action_payload=sample_calls()["payment_processor_sim"][1],
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
    """Uses the SAME functions as execution_service: get_tool_implementation (finds the tool and gives it our grant
    verifier) and _call_tool (runs it with a time limit and understands its answers and errors)."""
    from app.services import execution_service as es

    print("\nTools (as execution_service finds and calls them)")
    samples = sample_calls()
    try:
        registered = sorted(es._tool_registry())
        print(f"  tool names registered by app.tools.build_tool_registry: {registered}")
        unexpected = [n for n in registered if n not in SEED_TOOL_NAMES]
        if unexpected:
            print(f"  NOTE: these names are not in the specification or the database seed: {unexpected}")
            print(f"        governance looks tools up by the seeded names: {SEED_TOOL_NAMES}")
    except Exception as exc:  # noqa: BLE001
        print(f"  could not list the registered tools: {type(exc).__name__}: {str(exc)[:120]}")
    for name in SEED_TOOL_NAMES:
        tool = es.get_tool_implementation(name)
        if not check(tool is not None, f"a tool is registered under the name {name}",
                     "execution of this tool would end FAILED / TOOL_NOT_AVAILABLE. Ask Student 2 to build it"):
            continue
        action_type, payload = samples[name]
        invocation = ToolInvocationRequest(execution_id=uuid.uuid4(), action_id=uuid.uuid4(), tool_name=name,
                                           action_type=ActionType(action_type), action_payload=payload)
        grant = mint_execution_grant(invocation.execution_id, invocation.action_id, name, compute_payload_hash(payload))
        try:
            result = await es._call_tool(tool, invocation, grant, timeout=5.0)
            check(result.success, f"  {name} runs with a valid grant",
                  f"it failed: {result.error_code} {result.error_message}")
        except Exception as exc:  # noqa: BLE001
            check(False, f"  {name} runs with a valid grant", f"{type(exc).__name__}: {str(exc)[:140]}")
            continue
        try:
            again = await es._call_tool(tool, invocation, grant, timeout=5.0)
            check(not again.success, f"  {name} refuses the same grant a second time",
                  "the tool ran twice with one grant: single use is not enforced")
        except Exception:  # noqa: BLE001 - any refusal is what we want
            check(True, f"  {name} refuses the same grant a second time")
        other, fresh = invocation.model_copy(update={"action_payload": {**payload, "__tampered": True}}), None
        fresh = mint_execution_grant(invocation.execution_id, invocation.action_id, name, compute_payload_hash(payload))
        try:
            tampered = await es._call_tool(tool, other, fresh, timeout=5.0)
            check(not tampered.success, f"  {name} refuses a payload that differs from the one the grant was issued for",
                  "the tool ran with a changed payload")
        except Exception:  # noqa: BLE001
            check(True, f"  {name} refuses a payload that differs from the one the grant was issued for")
        try:
            none_grant = await es._call_tool(tool, invocation, None, timeout=5.0)
            check(not none_grant.success, f"  {name} refuses to run without a grant", "a tool must fail closed without a grant")
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
