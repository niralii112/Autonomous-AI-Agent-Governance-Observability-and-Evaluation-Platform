import ast
import itertools
import json
import re
import uuid
from pathlib import Path

import pytest

from app.core.enums import (
    AgentStatus, ErrorCode, GovernanceDecision as GD, PolicyResult as PR, RiskLevel, RiskSource, ToolSensitivity, ToolStatus,
)
from app.schemas import GovernanceDecisionRequest, PolicyEvaluationResponse, RiskAssessmentResponse
from app.services import decision_service
from app.services.decision_service import make_governance_decision

EXAMPLES = Path(__file__).resolve().parents[4] / "contracts" / "examples"
RISK_TEMPLATE = json.loads((EXAMPLES / "RSK-01.response.json").read_text())
VECTORS = json.loads((EXAMPLES / "decision" / "decision-test-vectors.json").read_text())["vectors"]
STRICTNESS = {GD.ALLOW: 0, GD.HUMAN_REVIEW: 1, GD.BLOCK: 2}


# ================================ builders ===========================================================

def policy_eval(result: PR) -> PolicyEvaluationResponse:
    return PolicyEvaluationResponse(
        policy_result=result, matched_policies=[], winning_policy_id=None, conflict_detected=False,
        evaluated_policy_count=0, policy_snapshot_hash="0" * 64,
        error_code=ErrorCode.POLICY_ENGINE_FAILURE if result == PR.ERROR else None, latency_ms=0.0)


_risk_cache: dict = {}


def risk(level: str | None, source: str | None = "ML_MODEL") -> RiskAssessmentResponse | None:
    if level is None:
        return None
    key = (level, source)
    if key not in _risk_cache:
        _risk_cache[key] = RiskAssessmentResponse.model_validate({**RISK_TEMPLATE, "risk_level": level, "risk_source": source})
    return _risk_cache[key]


def request(*, policy="ALLOW", level="LOW", source="ML_MODEL", sensitivity="READ_ONLY", agent="ACTIVE", found=True,
            tool_status="ACTIVE", permitted=True, no_match="HUMAN_REVIEW") -> GovernanceDecisionRequest:
    return GovernanceDecisionRequest(
        action_id=str(uuid.uuid4()), agent_status=AgentStatus(agent), tool_found=found,
        tool_status=ToolStatus(tool_status) if tool_status else None, agent_tool_permitted=permitted,
        tool_sensitivity=ToolSensitivity(sensitivity) if sensitivity else None, policy_evaluation=policy_eval(PR(policy)),
        risk_assessment=risk(level, source), no_match_decision=GD(no_match))


def decide(**kw):
    out = make_governance_decision(request(**kw))
    return out.final_decision.value, out.decision_reason_code, out.decision_rule_id


# ================================ the contract's 94 test vectors ======================================

def request_from_vector(v: dict) -> GovernanceDecisionRequest:
    o = v.get("overrides", {})
    return request(
        policy=v["policy_result"], level=v["risk_level"], source=v["risk_source"],
        sensitivity=v.get("tool_sensitivity"),
        agent=v.get("agent_status", "DISABLED" if o.get("agent_active") is False else "ACTIVE"),
        found=v.get("tool_found", o.get("tool_found", True)),
        tool_status=v.get("tool_status", "DISABLED" if o.get("tool_active") is False else "ACTIVE"),
        permitted=v.get("agent_tool_permitted", o.get("permitted", True)),
        no_match=v.get("no_match_decision", "HUMAN_REVIEW"))


def test_there_are_94_vectors_covering_every_rule():
    assert len(VECTORS) == 94
    assert {v["expected"]["decision_rule_id"] for v in VECTORS} == {f"D-{n:02d}" for n in range(1, 14)}


@pytest.mark.parametrize("vector", VECTORS, ids=[f"{i:02d}-{v['expected']['decision_rule_id']}" for i, v in enumerate(VECTORS)])
def test_contract_vector(vector):
    out = make_governance_decision(request_from_vector(vector))
    expected = vector["expected"]
    assert (out.final_decision.value, out.decision_reason_code, out.decision_rule_id) == (
        expected["final_decision"], expected["decision_reason_code"], expected["decision_rule_id"])


# ================================ each rule, by hand ====================================================

@pytest.mark.parametrize("kw,expected", [
    (dict(agent="DISABLED"), ("BLOCK", "AGENT_DISABLED", "D-01")),
    (dict(found=False, tool_status=None, sensitivity=None), ("BLOCK", "TOOL_UNKNOWN", "D-02")),
    (dict(tool_status="DISABLED"), ("BLOCK", "TOOL_DISABLED", "D-03")),
    (dict(tool_status=None), ("BLOCK", "TOOL_DISABLED", "D-03")),           # a missing status is not ACTIVE
    (dict(permitted=False), ("BLOCK", "AGENT_TOOL_NOT_PERMITTED", "D-04")),
    (dict(policy="ERROR"), ("BLOCK", "POLICY_ENGINE_FAILURE", "D-05")),
    (dict(policy="BLOCK"), ("BLOCK", "POLICY_BLOCK", "D-06")),
    (dict(policy="ALLOW", level="CRITICAL"), ("BLOCK", "RISK_CRITICAL_BLOCK", "D-07")),
    (dict(policy="HUMAN_REVIEW", level="LOW"), ("HUMAN_REVIEW", "POLICY_REVIEW_REQUIRED", "D-08")),
    (dict(policy="NO_MATCH", level="LOW"), ("HUMAN_REVIEW", "NO_POLICY_MATCH_REVIEW", "D-09")),
    (dict(policy="NO_MATCH", level="LOW", no_match="BLOCK"), ("BLOCK", "NO_POLICY_MATCH_BLOCK", "D-09")),
    (dict(policy="ALLOW", level=None, source=None), ("HUMAN_REVIEW", "RISK_UNAVAILABLE_REVIEW", "D-10")),
    (dict(policy="ALLOW", level="HIGH"), ("HUMAN_REVIEW", "RISK_HIGH_REVIEW", "D-11")),
    (dict(policy="ALLOW", level="LOW", source="HEURISTIC_FALLBACK", sensitivity="WRITE"), ("HUMAN_REVIEW", "FALLBACK_RISK_SENSITIVE_REVIEW", "D-12")),
    (dict(policy="ALLOW", level="MEDIUM", source="HEURISTIC_FALLBACK", sensitivity="PRIVILEGED"), ("HUMAN_REVIEW", "FALLBACK_RISK_SENSITIVE_REVIEW", "D-12")),
    (dict(policy="ALLOW", level="LOW"), ("ALLOW", "POLICY_ALLOW_LOW_RISK", "D-13")),
    (dict(policy="ALLOW", level="MEDIUM"), ("ALLOW", "POLICY_ALLOW_MEDIUM_RISK", "D-13")),
])
def test_each_rule(kw, expected):
    assert decide(**kw) == expected


@pytest.mark.parametrize("sensitivity", ["READ_ONLY", "SENSITIVE_READ"])
def test_a_fallback_risk_may_still_auto_approve_non_write_tools(sensitivity):
    assert decide(policy="ALLOW", level="LOW", source="HEURISTIC_FALLBACK", sensitivity=sensitivity)[2] == "D-13"


# ================================ order: the first matching rule wins ====================================

def test_a_disabled_agent_beats_everything_else():
    assert decide(agent="DISABLED", found=False, tool_status="DISABLED", permitted=False, policy="ERROR", level="CRITICAL")[2] == "D-01"


def test_precedence_chain_d02_d03_d04():
    assert decide(found=False, tool_status="DISABLED", permitted=False)[2] == "D-02"
    assert decide(tool_status="DISABLED", permitted=False)[2] == "D-03"
    assert decide(permitted=False, policy="ERROR")[2] == "D-04"


def test_engine_failure_beats_a_policy_block_and_critical_risk():
    assert decide(policy="ERROR", level="CRITICAL")[2] == "D-05"


def test_policy_block_ignores_risk_completely():
    assert {decide(policy="BLOCK", level=lv, source=src)[2] for lv in (None, "LOW", "MEDIUM", "HIGH", "CRITICAL")
            for src in ("ML_MODEL", "HEURISTIC_FALLBACK")} == {"D-06"}


@pytest.mark.parametrize("policy", ["HUMAN_REVIEW", "NO_MATCH", "ALLOW"])
def test_critical_risk_blocks_whatever_the_policy_asked_for(policy):
    assert decide(policy=policy, level="CRITICAL")[:3:2] == ("BLOCK", "D-07")


def test_high_risk_is_checked_before_the_fallback_rule():
    assert decide(policy="ALLOW", level="HIGH", source="HEURISTIC_FALLBACK", sensitivity="WRITE")[2] == "D-11"


# ================================ default deny and safe corners ===========================================

@pytest.mark.parametrize("no_match", ["HUMAN_REVIEW", "BLOCK", "ALLOW"])
@pytest.mark.parametrize("level", [None, "LOW", "MEDIUM", "HIGH"])
def test_no_policy_match_can_never_become_allow_even_if_misconfigured(no_match, level):
    assert decide(policy="NO_MATCH", level=level, source="ML_MODEL" if level else None, no_match=no_match)[0] != "ALLOW"


def test_a_misconfigured_allow_for_no_match_becomes_review():
    assert decide(policy="NO_MATCH", no_match="ALLOW") == ("HUMAN_REVIEW", "NO_POLICY_MATCH_REVIEW", "D-09")


def test_unknown_tool_sensitivity_changes_nothing_except_d12():
    assert decide(policy="ALLOW", level="LOW", sensitivity=None)[2] == "D-13"


# ================================ every possible input (finite, so we can check ALL of them) =================

AGENTS = ["ACTIVE", "DISABLED"]
FOUND = [True, False]
TOOL_STATUSES = ["ACTIVE", "DISABLED", None]
PERMITTED = [True, False]
POLICIES = ["ALLOW", "HUMAN_REVIEW", "BLOCK", "NO_MATCH", "ERROR"]
RISKS = [(None, None)] + [(lv, src) for lv in ("LOW", "MEDIUM", "HIGH", "CRITICAL") for src in ("ML_MODEL", "HEURISTIC_FALLBACK")]
SENSITIVITIES = [None, "READ_ONLY", "SENSITIVE_READ", "WRITE", "PRIVILEGED"]
NO_MATCH = ["HUMAN_REVIEW", "BLOCK", "ALLOW"]

PE = {p: policy_eval(PR(p)) for p in POLICIES}


def build(agent, found, ts, permitted, policy, rk, sens, nm):
    """model_construct skips re-validation: all objects used are already validated models."""
    return GovernanceDecisionRequest.model_construct(
        action_id="x", agent_status=AgentStatus(agent), tool_found=found, tool_status=ToolStatus(ts) if ts else None,
        agent_tool_permitted=permitted, tool_sensitivity=ToolSensitivity(sens) if sens else None,
        policy_evaluation=PE[policy], risk_assessment=risk(*rk) if rk[0] else None, no_match_decision=GD(nm))


ALL_INPUTS = list(itertools.product(AGENTS, FOUND, TOOL_STATUSES, PERMITTED, POLICIES, RISKS, SENSITIVITIES, NO_MATCH))
ALLOWED_PAIRS = {
    "D-01": {("BLOCK", "AGENT_DISABLED")}, "D-02": {("BLOCK", "TOOL_UNKNOWN")}, "D-03": {("BLOCK", "TOOL_DISABLED")},
    "D-04": {("BLOCK", "AGENT_TOOL_NOT_PERMITTED")}, "D-05": {("BLOCK", "POLICY_ENGINE_FAILURE")},
    "D-06": {("BLOCK", "POLICY_BLOCK")}, "D-07": {("BLOCK", "RISK_CRITICAL_BLOCK")},
    "D-08": {("HUMAN_REVIEW", "POLICY_REVIEW_REQUIRED")},
    "D-09": {("HUMAN_REVIEW", "NO_POLICY_MATCH_REVIEW"), ("BLOCK", "NO_POLICY_MATCH_BLOCK")},
    "D-10": {("HUMAN_REVIEW", "RISK_UNAVAILABLE_REVIEW")}, "D-11": {("HUMAN_REVIEW", "RISK_HIGH_REVIEW")},
    "D-12": {("HUMAN_REVIEW", "FALLBACK_RISK_SENSITIVE_REVIEW")},
    "D-13": {("ALLOW", "POLICY_ALLOW_LOW_RISK"), ("ALLOW", "POLICY_ALLOW_MEDIUM_RISK")},
}


def run(inputs):
    return make_governance_decision(build(*inputs))


def test_the_input_space_is_what_we_think_it_is():
    assert len(ALL_INPUTS) == 2 * 2 * 3 * 2 * 5 * 9 * 5 * 3 == 16200


def test_total_function_with_valid_outputs_and_paired_codes():
    for inputs in ALL_INPUTS:
        out = run(inputs)
        assert re.fullmatch(r"D-[0-9]{2}", out.decision_rule_id)
        assert (out.final_decision.value, out.decision_reason_code) in ALLOWED_PAIRS[out.decision_rule_id], inputs


def test_deterministic():
    for inputs in ALL_INPUTS[::7]:
        assert run(inputs) == run(inputs)


def test_allow_is_only_ever_produced_by_d13_and_only_when_everything_is_in_order():
    allowed = 0
    for inputs in ALL_INPUTS:
        agent, found, ts, permitted, policy, (level, source), sens, nm = inputs
        out = run(inputs)
        if out.final_decision != GD.ALLOW:
            continue
        allowed += 1
        assert out.decision_rule_id == "D-13", inputs
        assert (agent, found, ts, permitted, policy) == ("ACTIVE", True, "ACTIVE", True, "ALLOW"), inputs
        assert level in ("LOW", "MEDIUM"), inputs
        assert not (source == "HEURISTIC_FALLBACK" and sens in ("WRITE", "PRIVILEGED")), inputs
    assert allowed > 0


def test_blocking_facts_always_block():
    for inputs in ALL_INPUTS:
        agent, found, ts, permitted, policy, *_ = inputs
        if agent != "ACTIVE" or not found or ts != "ACTIVE" or not permitted or policy in ("ERROR", "BLOCK"):
            assert run(inputs).final_decision == GD.BLOCK, inputs


def test_a_policy_asking_for_review_or_no_match_never_ends_in_allow():
    for inputs in ALL_INPUTS:
        if inputs[4] in ("HUMAN_REVIEW", "NO_MATCH", "BLOCK", "ERROR"):
            assert run(inputs).final_decision != GD.ALLOW, inputs


def test_rules_d01_to_d06_do_not_depend_on_risk_at_all():
    """Spec 13.4: for every input matched by D-01..D-06 the outcome is independent of risk_assessment."""
    seen = 0
    for agent, found, ts, permitted, policy, rk, sens, nm in ALL_INPUTS:
        out = run((agent, found, ts, permitted, policy, rk, sens, nm))
        if out.decision_rule_id > "D-06":
            continue
        seen += 1
        assert all(run((agent, found, ts, permitted, policy, other, sens, nm)) == out for other in RISKS), (agent, found, ts, permitted, policy)
    assert seen > 0


def test_higher_risk_never_gives_a_less_restrictive_decision():
    """Spec 13.4, monotonic restriction: LOW <= MEDIUM <= HIGH <= CRITICAL, same source."""
    levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    for agent, found, ts, permitted, policy, _, sens, nm in itertools.product(AGENTS, FOUND, TOOL_STATUSES, PERMITTED, POLICIES, [0], SENSITIVITIES, NO_MATCH):
        for source in ("ML_MODEL", "HEURISTIC_FALLBACK"):
            strictness = [STRICTNESS[run((agent, found, ts, permitted, policy, (lv, source), sens, nm)).final_decision] for lv in levels]
            assert strictness == sorted(strictness), (agent, found, ts, permitted, policy, source, sens, nm, strictness)


def test_missing_risk_is_never_less_restrictive_than_the_lowest_risk():
    """Missing risk never relaxes control."""
    for agent, found, ts, permitted, policy, _, sens, nm in itertools.product(AGENTS, FOUND, TOOL_STATUSES, PERMITTED, POLICIES, [0], SENSITIVITIES, NO_MATCH):
        none = STRICTNESS[run((agent, found, ts, permitted, policy, (None, None), sens, nm)).final_decision]
        for source in ("ML_MODEL", "HEURISTIC_FALLBACK"):
            lowest = STRICTNESS[run((agent, found, ts, permitted, policy, ("LOW", source), sens, nm)).final_decision]
            assert none >= lowest, (agent, found, ts, permitted, policy, sens, nm)


def test_a_fallback_risk_is_never_less_restrictive_than_an_ml_risk_of_the_same_level():
    for agent, found, ts, permitted, policy, _, sens, nm in itertools.product(AGENTS, FOUND, TOOL_STATUSES, PERMITTED, POLICIES, [0], SENSITIVITIES, NO_MATCH):
        for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            ml = STRICTNESS[run((agent, found, ts, permitted, policy, (level, "ML_MODEL"), sens, nm)).final_decision]
            fb = STRICTNESS[run((agent, found, ts, permitted, policy, (level, "HEURISTIC_FALLBACK"), sens, nm)).final_decision]
            assert fb >= ml


def test_every_rule_is_reachable():
    assert {run(i).decision_rule_id for i in ALL_INPUTS} == {f"D-{n:02d}" for n in range(1, 14)}


# ================================ purity ==============================================================

def test_the_module_imports_nothing_that_could_do_io_or_read_a_clock():
    tree = ast.parse(Path(decision_service.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"app"}, imported  # only our own enums and schemas; no sqlalchemy, time, datetime, random, os, logging...


def test_the_function_is_synchronous():
    import inspect
    assert not inspect.iscoroutinefunction(make_governance_decision)


def test_the_input_is_not_modified():
    r = request(policy="ALLOW", level="LOW")
    before = r.model_dump()
    make_governance_decision(r)
    assert r.model_dump() == before


# ================================ speed (spec NFR-04: decision + policy evaluation under 50 ms p95) ==========

def test_a_decision_takes_microseconds():
    import time
    r = request(policy="ALLOW", level="LOW")
    started = time.perf_counter()
    for _ in range(5000):
        make_governance_decision(r)
    per_call_ms = (time.perf_counter() - started) / 5000 * 1000
    assert per_call_ms < 1.0, per_call_ms  # about 1000x below the 50 ms budget, even on a slow laptop
