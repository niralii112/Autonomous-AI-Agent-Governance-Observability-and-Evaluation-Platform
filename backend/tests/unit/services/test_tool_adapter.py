"""The adapter between execution_service and Student 2's tools (spec 12.7 plus her real tool design)."""

import asyncio
import sys
import threading
import time
import types
import uuid

import pytest

from app.core.config import get_settings
from app.core.enums import ActionType, ErrorCode
from app.core.execution_grant import mint_execution_grant, reset_nonce_store
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas import ToolInvocationRequest, ToolInvocationResult
from app.services import execution_service as es
from tests.tool_doubles import StudentStyleTool, ToolInvocationError

PAYLOAD = {"payee_id": "payee-0001", "amount": 450, "currency": "USD", "reference": "inv-1"}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    get_settings.cache_clear()
    reset_nonce_store()
    es._tool_registry.cache_clear()
    yield
    es._tool_registry.cache_clear()
    reset_nonce_store()
    get_settings.cache_clear()


def call(tool_name="payment_processor_sim"):
    invocation = ToolInvocationRequest(execution_id=uuid.uuid4(), action_id=uuid.uuid4(), tool_name=tool_name,
                                       action_type=ActionType.FINANCE_PROPOSE_PAYMENT, action_payload=PAYLOAD)
    grant = mint_execution_grant(invocation.execution_id, invocation.action_id, tool_name, compute_payload_hash(PAYLOAD))
    return invocation, grant


# ================================ the verifier we hand to the tools ============================================

def test_the_verifier_accepts_a_good_grant_and_returns_true():
    invocation, grant = call()
    assert es._grant_verifier(grant, invocation) is True


def test_the_verifier_raises_for_a_forged_grant():
    invocation, grant = call()
    with pytest.raises(AppError):
        es._grant_verifier(grant.model_copy(update={"signature": "0" * 64}), invocation)


def test_the_verifier_allows_a_grant_only_once():
    invocation, grant = call()
    es._grant_verifier(grant, invocation)
    with pytest.raises(AppError):
        es._grant_verifier(grant, invocation)


def test_the_verifier_refuses_a_changed_payload():
    invocation, grant = call()
    with pytest.raises(AppError):
        es._grant_verifier(grant, invocation.model_copy(update={"action_payload": {**PAYLOAD, "amount": 99999}}))


# ================================ turning tool answers into results ============================================

def test_a_typed_result_passes_through():
    result = ToolInvocationResult(success=True, output={"a": 1}, error_code=None, error_message=None)
    assert es._normalize_tool_result(result) is result


def test_a_success_dict_uses_its_output():
    got = es._normalize_tool_result({"success": True, "tool_name": "t", "execution_id": "e", "output": {"done": 1}})
    assert (got.success, got.output) == (True, {"done": 1})


@pytest.mark.parametrize("raw,expected", [({"success": True}, {}), ({"success": True, "output": [1, 2]}, {"output": [1, 2]})])
def test_odd_but_successful_outputs_are_kept_as_a_dict(raw, expected):
    assert es._normalize_tool_result(raw).output == expected


@pytest.mark.parametrize("raw,code,message", [
    ({"success": False, "error_code": "TOOL_EXECUTION_FAILED", "error_message": "declined"}, ErrorCode.TOOL_EXECUTION_FAILED, "declined"),
    ({"success": False, "error_code": "TOOL_NOT_AVAILABLE"}, ErrorCode.TOOL_NOT_AVAILABLE, "The tool reported a failure."),
    ({"success": False, "error_code": "MADE_UP_CODE", "message": "nope"}, ErrorCode.TOOL_EXECUTION_FAILED, "nope"),
    ({"success": False}, ErrorCode.TOOL_EXECUTION_FAILED, "The tool reported a failure."),
])
def test_a_failure_dict_becomes_a_failed_result(raw, code, message):
    got = es._normalize_tool_result(raw)
    assert (got.success, got.error_code, got.error_message) == (False, code, message)


def test_very_long_failure_messages_are_cut():
    assert len(es._normalize_tool_result({"success": False, "error_message": "x" * 5000}).error_message) == 500


@pytest.mark.parametrize("raw", ["oops", None, 42, [], {}, {"output": {"a": 1}}, {"success": "yes"}])
def test_anything_else_is_not_a_result(raw):
    with pytest.raises(TypeError):
        es._normalize_tool_result(raw)


# ================================ calling a tool ==================================================================

async def test_a_plain_synchronous_tool_works_and_runs_off_the_event_loop_thread():
    seen = {}

    class Probe(StudentStyleTool):
        def invoke(self, request, grant):
            seen["thread"] = threading.current_thread().name
            return super().invoke(request, grant)

    tool = Probe("payment_processor_sim", es._grant_verifier)
    invocation, grant = call()
    result = await es._call_tool(tool, invocation, grant, timeout=5)
    assert result.success and result.output == {"simulated": True}
    assert seen["thread"] != threading.main_thread().name


async def test_an_async_tool_is_awaited_directly():
    class AsyncTool:
        async def invoke(self, invocation, grant):
            return ToolInvocationResult(success=True, output={"x": 1}, error_code=None, error_message=None)

    invocation, grant = call()
    assert (await es._call_tool(AsyncTool(), invocation, grant, timeout=5)).output == {"x": 1}


async def test_a_tool_error_with_a_code_becomes_a_failed_result():
    tool = StudentStyleTool("payment_processor_sim", es._grant_verifier, behaviour="invalid_payload")
    invocation, grant = call()
    result = await es._call_tool(tool, invocation, grant, timeout=5)
    assert (result.success, result.error_code, result.error_message) == (False, ErrorCode.TOOL_EXECUTION_FAILED, "The tool payload is invalid.")


async def test_a_tool_built_without_a_verifier_refuses_to_run():
    tool = StudentStyleTool("payment_processor_sim", None)
    invocation, grant = call()
    result = await es._call_tool(tool, invocation, grant, timeout=5)
    assert (result.success, result.error_code) == (False, ErrorCode.EXECUTION_GRANT_INVALID) and tool.calls == []


async def test_a_reused_grant_is_refused_by_the_tool():
    tool = StudentStyleTool("payment_processor_sim", es._grant_verifier)
    invocation, grant = call()
    assert (await es._call_tool(tool, invocation, grant, timeout=5)).success
    second = await es._call_tool(tool, invocation, grant, timeout=5)
    assert (second.success, second.error_code) == (False, ErrorCode.EXECUTION_GRANT_INVALID) and len(tool.calls) == 1


async def test_an_unexpected_exception_propagates_for_the_caller_to_handle():
    tool = StudentStyleTool("payment_processor_sim", es._grant_verifier, behaviour="crash")
    invocation, grant = call()
    with pytest.raises(RuntimeError):
        await es._call_tool(tool, invocation, grant, timeout=5)


async def test_a_slow_synchronous_tool_times_out_without_freezing_the_event_loop():
    tool = StudentStyleTool("payment_processor_sim", es._grant_verifier, behaviour="slow", delay=2.0)
    invocation, grant = call()
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    started = time.perf_counter()
    with pytest.raises(asyncio.TimeoutError):
        await es._call_tool(tool, invocation, grant, timeout=0.3)
    elapsed = time.perf_counter() - started
    beat.cancel()
    assert elapsed < 1.0 and ticks >= 3  # we gave up after 0.3 s, and other work kept running meanwhile


# ================================ finding a tool ==================================================================

def fake_tools_package(monkeypatch, behaviour="ok"):
    built = {}

    def build_tool_registry(grant_verifier=None):
        built["verifier"] = grant_verifier
        return {"payment_processor_sim": StudentStyleTool("payment_processor_sim", grant_verifier, behaviour)}

    package = types.ModuleType("app.tools")
    package.build_tool_registry = build_tool_registry
    monkeypatch.setitem(sys.modules, "app.tools", package)
    monkeypatch.delitem(sys.modules, "app.tools.registry", raising=False)
    return built


def test_the_registry_is_built_with_our_verifier_and_a_known_tool_is_found(monkeypatch):
    built = fake_tools_package(monkeypatch)
    tool = es.get_tool_implementation("payment_processor_sim")
    assert tool is not None and tool.tool_name == "payment_processor_sim" and built["verifier"] is es._grant_verifier


def test_an_unknown_tool_name_gives_none(monkeypatch):
    fake_tools_package(monkeypatch)
    assert es.get_tool_implementation("no_such_tool") is None
    assert es.get_tool_implementation("ticket_reader") is None  # read-only tools Student 2 has not built yet


def test_the_registry_is_built_only_once(monkeypatch):
    built = fake_tools_package(monkeypatch)
    first = es.get_tool_implementation("payment_processor_sim")
    built.clear()
    assert es.get_tool_implementation("payment_processor_sim") is first and built == {}


def test_if_the_tools_package_cannot_be_imported_nothing_is_found(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.tools", None)  # makes `import app.tools` raise ImportError
    assert es.get_tool_implementation("payment_processor_sim") is None


def test_the_specified_registry_module_wins_when_it_exists(monkeypatch):
    fake_tools_package(monkeypatch)
    registry = types.ModuleType("app.tools.registry")
    registry.get_tool_implementation = lambda name: f"from-spec-registry:{name}"
    monkeypatch.setitem(sys.modules, "app.tools.registry", registry)
    assert es.get_tool_implementation("anything") == "from-spec-registry:anything"
