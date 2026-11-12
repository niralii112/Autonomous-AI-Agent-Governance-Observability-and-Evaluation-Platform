import json
from pathlib import Path

import pytest

from app.agents.scenarios import (
    SCENARIO_SPECS,
    get_scenario_spec,
    scenarios_for_category,
)
from app.core.enums import AgentCategory, GovernanceDecision
from app.schemas.action_payloads import ACTION_PAYLOAD_MODELS
from app.tools import build_tool_registry

CATALOG_FILE = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "examples"
    / "scenarios"
    / "scenario-catalog.json"
)


def load_catalog() -> list[dict]:
    data = json.loads(CATALOG_FILE.read_text())
    scenarios = data["scenarios"] if isinstance(data, dict) else data
    # IT Operations is not part of our project.
    return [item for item in scenarios if not item["scenario_key"].startswith("it.")]


CATALOG = load_catalog()


def test_there_are_thirteen_scenarios():
    assert len(SCENARIO_SPECS) == 13
    assert len(scenarios_for_category(AgentCategory.FINANCE)) == 8
    assert len(scenarios_for_category(AgentCategory.CUSTOMER_SUPPORT)) == 5


def test_scenario_keys_are_unique():
    keys = [spec.scenario.scenario_key for spec in SCENARIO_SPECS]

    assert len(keys) == len(set(keys))


def test_scenarios_match_the_catalog_exactly():
    by_key = {item["scenario_key"]: item for item in CATALOG}

    assert set(by_key) == {spec.scenario.scenario_key for spec in SCENARIO_SPECS}

    for spec in SCENARIO_SPECS:
        item = by_key[spec.scenario.scenario_key]

        assert spec.scenario.action_type.value == item["action_type"]
        assert spec.scenario.tool_name == item["tool_name"]
        assert spec.scenario.action_payload == item["action_payload"]
        assert spec.scenario.expected_decision.value == item["expected_decision_ml_model"]
        assert (
            spec.decision_with_heuristic.value == item["expected_decision_heuristic_fallback"]
        )
        assert spec.heuristic_risk_level.value == item["heuristic_risk_level"]
        assert [level.value for level in spec.acceptance_levels] == item[
            "ml_model_acceptance_levels"
        ]


@pytest.mark.parametrize(
    "spec", SCENARIO_SPECS, ids=lambda spec: spec.scenario.scenario_key
)
def test_payload_follows_the_contract(spec):
    model = ACTION_PAYLOAD_MODELS[spec.scenario.action_type]

    model.model_validate(spec.scenario.action_payload)


@pytest.mark.parametrize(
    "spec", SCENARIO_SPECS, ids=lambda spec: spec.scenario.scenario_key
)
def test_scenario_uses_a_registered_tool_for_its_action_type(spec):
    registry = build_tool_registry()

    assert spec.scenario.tool_name in registry


@pytest.mark.parametrize(
    "spec", SCENARIO_SPECS, ids=lambda spec: spec.scenario.scenario_key
)
def test_scenario_belongs_to_its_agent_category(spec):
    prefix = {
        AgentCategory.FINANCE: "finance.",
        AgentCategory.CUSTOMER_SUPPORT: "support.",
    }[spec.agent_category]

    assert spec.scenario.scenario_key.startswith(prefix)


def test_get_scenario_spec_finds_and_misses():
    found = get_scenario_spec(AgentCategory.FINANCE, "finance.payment.small")

    assert found is not None
    assert found.scenario.expected_decision == GovernanceDecision.ALLOW
    assert get_scenario_spec(AgentCategory.FINANCE, "support.ticket.get") is None
    assert get_scenario_spec(AgentCategory.CUSTOMER_SUPPORT, "nope") is None


def test_blocked_scenarios_are_blocked_whatever_the_risk():
    blocked = [
        spec
        for spec in SCENARIO_SPECS
        if spec.scenario.expected_decision == GovernanceDecision.BLOCK
    ]

    assert blocked
    for spec in blocked:
        # A rule block must hold even when the heuristic says the risk is low.
        assert spec.decision_with_heuristic == GovernanceDecision.BLOCK
