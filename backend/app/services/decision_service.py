"""The decision engine: make_governance_decision (spec 12.6 and 13.4).

A PURE function: no database, no clock, no randomness, no logging, no exceptions. The same input
always gives the same output. It checks rules D-01 to D-13 in order and the FIRST rule that fits wins.

How to read the rules:
  D-01..D-04  the agent, tool and permission must be fine, or the action is blocked.
  D-05..D-06  a policy engine failure or a policy BLOCK is blocked. Risk is not even looked at.
  D-07        a CRITICAL risk blocks, whatever the policies said.
  D-08..D-09  policy review, or "no policy matched" (default-deny), needs a human.
  D-10..D-13  the ONLY way to ALLOW: an explicit ALLOW policy, plus a known, acceptable risk.

Risk can only add restriction, never remove it ("monotonic restriction").
"""

from app.core.enums import (
    AgentStatus, GovernanceDecision, PolicyResult, RiskLevel, RiskSource, ToolSensitivity, ToolStatus,
)
from app.schemas import GovernanceDecisionOutcome, GovernanceDecisionRequest

_SENSITIVE_FOR_FALLBACK = {ToolSensitivity.WRITE, ToolSensitivity.PRIVILEGED}


def _outcome(decision: GovernanceDecision, reason: str, rule: str) -> GovernanceDecisionOutcome:
    return GovernanceDecisionOutcome(final_decision=decision, decision_reason_code=reason, decision_rule_id=rule)


def make_governance_decision(request: GovernanceDecisionRequest) -> GovernanceDecisionOutcome:
    result = request.policy_evaluation.policy_result
    risk = request.risk_assessment

    if request.agent_status != AgentStatus.ACTIVE:                                  # D-01
        return _outcome(GovernanceDecision.BLOCK, "AGENT_DISABLED", "D-01")
    if not request.tool_found:                                                      # D-02
        return _outcome(GovernanceDecision.BLOCK, "TOOL_UNKNOWN", "D-02")
    if request.tool_status != ToolStatus.ACTIVE:                                    # D-03 (a missing status is not ACTIVE)
        return _outcome(GovernanceDecision.BLOCK, "TOOL_DISABLED", "D-03")
    if not request.agent_tool_permitted:                                            # D-04
        return _outcome(GovernanceDecision.BLOCK, "AGENT_TOOL_NOT_PERMITTED", "D-04")
    if result == PolicyResult.ERROR:                                                # D-05 fail closed
        return _outcome(GovernanceDecision.BLOCK, "POLICY_ENGINE_FAILURE", "D-05")
    if result == PolicyResult.BLOCK:                                                # D-06 risk ignored entirely
        return _outcome(GovernanceDecision.BLOCK, "POLICY_BLOCK", "D-06")
    if risk is not None and risk.risk_level == RiskLevel.CRITICAL:                  # D-07
        return _outcome(GovernanceDecision.BLOCK, "RISK_CRITICAL_BLOCK", "D-07")
    if result == PolicyResult.HUMAN_REVIEW:                                         # D-08
        return _outcome(GovernanceDecision.HUMAN_REVIEW, "POLICY_REVIEW_REQUIRED", "D-08")
    if result == PolicyResult.NO_MATCH:                                             # D-09 default-deny
        if request.no_match_decision == GovernanceDecision.BLOCK:
            return _outcome(GovernanceDecision.BLOCK, "NO_POLICY_MATCH_BLOCK", "D-09")
        # HUMAN_REVIEW is the default. An ALLOW here would be a misconfiguration (the settings
        # refuse to start with it), and this function must never turn "no policy" into ALLOW.
        return _outcome(GovernanceDecision.HUMAN_REVIEW, "NO_POLICY_MATCH_REVIEW", "D-09")

    if result == PolicyResult.ALLOW:
        if risk is None:                                                            # D-10 missing risk never relaxes control
            return _outcome(GovernanceDecision.HUMAN_REVIEW, "RISK_UNAVAILABLE_REVIEW", "D-10")
        if risk.risk_level == RiskLevel.HIGH:                                       # D-11
            return _outcome(GovernanceDecision.HUMAN_REVIEW, "RISK_HIGH_REVIEW", "D-11")
        if risk.risk_source == RiskSource.HEURISTIC_FALLBACK and request.tool_sensitivity in _SENSITIVE_FOR_FALLBACK:
            return _outcome(GovernanceDecision.HUMAN_REVIEW, "FALLBACK_RISK_SENSITIVE_REVIEW", "D-12")
        if risk.risk_level == RiskLevel.LOW:                                        # D-13 the only path to ALLOW
            return _outcome(GovernanceDecision.ALLOW, "POLICY_ALLOW_LOW_RISK", "D-13")
        if risk.risk_level == RiskLevel.MEDIUM:
            return _outcome(GovernanceDecision.ALLOW, "POLICY_ALLOW_MEDIUM_RISK", "D-13")

    # Unreachable while the enums are closed. If it ever happens, treat it like an engine failure.
    return _outcome(GovernanceDecision.BLOCK, "POLICY_ENGINE_FAILURE", "D-05")
