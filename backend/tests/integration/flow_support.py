"""Helpers for tests of the submit_action flow: a seeded world, a fake tool registry and a fake risk model."""

import asyncio
import importlib.util
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.enums import ErrorCode
from app.core.execution_grant import reset_nonce_store, verify_execution_grant
from app.schemas import RiskAssessmentResponse, ToolInvocationResult
from app.services import action_service, execution_service
from tests.integration.conftest import TEST_URL

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"
_spec = importlib.util.spec_from_file_location("seed_for_flow", Path(__file__).resolve().parents[2] / "scripts" / "seed.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)

RISK_TEMPLATE = json.loads((EXAMPLES / "RSK-01.response.json").read_text())
SCORES = {"LOW": 0.1, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 0.95}


class FakeTool:
    """Behaves like a tool built by Student 2: it verifies the grant first, then does its work."""

    def __init__(self, mode: str = "ok"):
        self.mode, self.calls = mode, []

    async def invoke(self, invocation, grant):
        verify_execution_grant(grant, invocation)  # a tool without a valid grant must not run
        self.calls.append(invocation)
        if self.mode == "ok":
            return ToolInvocationResult(success=True, output={"status": "done", "tool": invocation.tool_name},
                                        error_code=None, error_message=None)
        if self.mode == "fail":
            return ToolInvocationResult(success=False, output={}, error_code=ErrorCode.TOOL_EXECUTION_FAILED,
                                        error_message="The payment was declined.")
        if self.mode == "raise":
            raise RuntimeError("boom: secret internal detail")
        if self.mode == "hang":
            await asyncio.sleep(30)
        raise AssertionError(self.mode)


class FakeRisk:
    """A replacement for assess_risk whose answer the test controls."""

    def __init__(self):
        self.level, self.source, self.mode, self.model_version = "LOW", "ML_MODEL", "ok", "risk-logreg-1.0.0"
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        if self.mode == "raise":
            raise RuntimeError("model exploded")
        if self.mode == "hang":
            await asyncio.sleep(30)
        action_id = uuid.uuid4() if self.mode == "other_action" else request.action_id
        if self.mode == "not_an_assessment":
            return "LOW"
        if self.mode == "invalid_dict":
            return {"risk_level": "LOW"}
        response = RiskAssessmentResponse.model_validate({
            **RISK_TEMPLATE, "risk_assessment_id": str(uuid.uuid4()), "action_id": str(action_id),
            "risk_score": SCORES[self.level], "risk_level": self.level, "risk_source": self.source,
            "model_version": self.model_version, "created_at": datetime.now(timezone.utc).isoformat()})
        return response.model_dump(mode="json") if self.mode == "as_dict" else response


@pytest.fixture
def tools(monkeypatch):
    """The fake tool registry. Edit `tools[name]` to change a tool, or delete it to make it unavailable."""
    registry: dict[str, FakeTool] = {name: FakeTool() for name, *_ in seed.SEED_TOOLS}
    monkeypatch.setattr(execution_service, "get_tool_implementation", lambda name: registry.get(name))
    reset_nonce_store()
    yield registry
    reset_nonce_store()


@pytest.fixture
def risk(monkeypatch):
    fake = FakeRisk()
    monkeypatch.setattr(action_service, "_assess_risk", fake)
    return fake


@pytest.fixture
async def session_factory():
    eng = create_async_engine(TEST_URL, poolclass=NullPool)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


@pytest.fixture
async def world(session_factory):
    """Seeded tools, agents, permissions, policies and model versions."""
    async with session_factory() as s:
        await seed.seed_registry(s)
        await seed.seed_policies(s)
        await seed.seed_model_versions(s)
        await s.commit()


def pay_body(agent_id, amount=450, payee="payee-0001", key=None, tool="payment_processor_sim"):
    return {"agent_id": str(agent_id), "tool_name": tool, "action_type": "FINANCE_PROPOSE_PAYMENT",
            "action_payload": {"payee_id": payee, "amount": amount, "currency": "USD", "reference": "inv-1"},
            "idempotency_key": key or uuid.uuid4().hex}
