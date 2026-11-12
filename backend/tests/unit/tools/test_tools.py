import json
import uuid
from pathlib import Path

import pytest

from app.core.enums import ActionType
from app.schemas.tool_runtime import ExecutionGrant, ToolInvocationRequest
from app.tools import build_tool_registry

CATALOG_FILE = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "examples"
    / "scenarios"
    / "scenario-catalog.json"
)

EXPECTED_TOOL_NAMES = {
    "finance_report_reader",
    "finance_summary_generator",
    "payment_processor_sim",
    "finance_records_vault",
    "ticket_reader",
    "support_response_generator",
    "refund_processor_sim",
    "customer_info_accessor",
}


def load_scenarios() -> list[dict]:
    data = json.loads(CATALOG_FILE.read_text())
    scenarios = data["scenarios"] if isinstance(data, dict) else data
    # IT Operations is not part of our project.
    return [item for item in scenarios if not item["scenario_key"].startswith("it.")]


SCENARIOS = load_scenarios()


def allow_everything(grant, request):
    return True


def make_call(item):
    request = ToolInvocationRequest(
        execution_id=uuid.uuid4(),
        action_id=uuid.uuid4(),
        tool_name=item["tool_name"],
        action_type=ActionType(item["action_type"]),
        action_payload=item["action_payload"],
    )
    grant = ExecutionGrant(
        execution_id=request.execution_id,
        action_id=request.action_id,
        tool_name=request.tool_name,
        payload_hash="test-hash",
        expires_at="2099-01-01T00:00:00Z",
        nonce="test-nonce",
        signature="test-signature",
    )
    return request, grant


def test_registry_has_the_eight_seeded_tool_names():
    assert set(build_tool_registry()) == EXPECTED_TOOL_NAMES


def test_every_catalog_tool_is_registered():
    registry = build_tool_registry()

    for item in SCENARIOS:
        assert item["tool_name"] in registry


@pytest.mark.parametrize("item", SCENARIOS, ids=lambda item: item["scenario_key"])
def test_tool_runs_every_catalog_payload(item):
    tool = build_tool_registry(allow_everything)[item["tool_name"]]
    request, grant = make_call(item)

    result = tool.invoke(request, grant)

    assert result["success"] is True


@pytest.mark.parametrize("item", SCENARIOS, ids=lambda item: item["scenario_key"])
def test_tool_fails_closed_without_a_verifier(item):
    tool = build_tool_registry()[item["tool_name"]]
    request, grant = make_call(item)

    with pytest.raises(Exception):
        tool.invoke(request, grant)