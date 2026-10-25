"""Pure policy matching (spec 13.1 and 13.2). No database, no I/O: easy to test and deterministic.

Rules worth remembering
  * A missing payload value makes every operator except EXISTS false (so NEQ and NOT_IN on a
    missing value are false, not true). A null value counts as missing.
  * Comparisons are strict about types: true is not 1, and "1" is not 1. A number compared with
    a string is simply "not equal" (false for EQ), never an error.
  * A malformed condition raises ValueError. evaluate_policy turns that into policy_result
    ERROR, which the decision engine treats as BLOCK (fail closed).
"""

import hashlib
from dataclasses import dataclass
from typing import Any

from app.core.enums import PolicyEffect, PolicyOperator, PolicyResult
from app.schemas import MatchedPolicy, PolicyCondition, PolicyConditions
from app.services.policy_conditions import PAYLOAD_FIELD, check_leaf

MISSING = object()
_RESTRICTIVENESS = {PolicyEffect.BLOCK: 0, PolicyEffect.HUMAN_REVIEW: 1, PolicyEffect.ALLOW: 2}  # lower = stricter


@dataclass(frozen=True)
class EvalContext:
    """The facts about one proposed action that conditions can look at."""

    action_type: str
    agent_id: str
    agent_category: str
    tool_name: str
    tool_sensitivity: str | None
    action_payload: dict[str, Any]


def resolve(field: str, ctx: EvalContext) -> Any:
    """The value a condition field refers to, or MISSING."""
    if PAYLOAD_FIELD.match(field):
        current: Any = ctx.action_payload
        for segment in field.split(".")[1:]:
            if not isinstance(current, dict) or segment not in current:
                return MISSING
            current = current[segment]
        return MISSING if current is None else current
    value = getattr(ctx, field, MISSING)  # only allow-listed names reach here (check_leaf ran first)
    return MISSING if value is None else value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def same(a: Any, b: Any) -> bool:
    """Strict equality: booleans only equal booleans, numbers compare by value, strings by text."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return False


def leaf_matches(leaf: PolicyCondition, ctx: EvalContext) -> bool:
    message = check_leaf(leaf)
    if message is not None:  # allow-list and value types are re-checked at evaluation time
        raise ValueError(f"malformed condition on {leaf.field!r}: {message}")
    actual = resolve(leaf.field, ctx)
    op, expected = leaf.operator, leaf.value

    if op == PolicyOperator.EXISTS:
        return actual is not MISSING
    if actual is MISSING:
        return False
    if op == PolicyOperator.EQ:
        return same(actual, expected)
    if op == PolicyOperator.NEQ:
        return not same(actual, expected)
    if op == PolicyOperator.IN:
        return any(same(actual, item) for item in expected)
    if op == PolicyOperator.NOT_IN:
        return not any(same(actual, item) for item in expected)
    if not _is_number(actual):  # GT, GTE, LT, LTE need a number on both sides
        return False
    return {
        PolicyOperator.GT: actual > expected,
        PolicyOperator.GTE: actual >= expected,
        PolicyOperator.LT: actual < expected,
        PolicyOperator.LTE: actual <= expected,
    }[op]


def conditions_match(conditions: PolicyConditions, ctx: EvalContext) -> bool:
    """Every leaf in `all` is true AND (`any` is empty OR at least one leaf in `any` is true)."""
    if not conditions.all and not conditions.any:
        raise ValueError("a policy needs at least one condition")
    # Evaluate EVERY leaf first (no short-circuit), so a malformed condition is reported every
    # time and never hidden behind an earlier leaf that happens to be false.
    all_results = [leaf_matches(leaf, ctx) for leaf in conditions.all]
    any_results = [leaf_matches(leaf, ctx) for leaf in conditions.any]
    return all(all_results) and (not any_results or any(any_results))


def scope_applies(scope_agent_id: Any, scope_agent_category: str | None, scope_action_type: str | None,
                  ctx: EvalContext) -> bool:
    """A policy is considered only when every non-null scope equals the action's value."""
    if scope_agent_id is not None and str(scope_agent_id) != ctx.agent_id:
        return False
    if scope_agent_category is not None and scope_agent_category != ctx.agent_category:
        return False
    if scope_action_type is not None and scope_action_type != ctx.action_type:
        return False
    return True


def choose_winner(matched: list[MatchedPolicy]) -> tuple[PolicyResult, MatchedPolicy | None]:
    """Spec 13.2 steps 3 to 5."""
    if not matched:
        return PolicyResult.NO_MATCH, None
    mandatory = [m for m in matched if m.is_mandatory and m.effect == PolicyEffect.BLOCK]
    if mandatory:  # a mandatory BLOCK beats everything, whatever the priorities
        winner = min(mandatory, key=lambda m: (m.priority, m.policy_key))
        return PolicyResult.BLOCK, winner
    best_priority = min(m.priority for m in matched)  # lowest number = highest precedence
    group = [m for m in matched if m.priority == best_priority]
    winner = min(group, key=lambda m: (_RESTRICTIVENESS[m.effect], m.policy_key))
    return PolicyResult(winner.effect.value), winner


def conflict_detected(matched: list[MatchedPolicy]) -> bool:
    return len({m.effect for m in matched}) > 1


def snapshot_hash(matched: list[MatchedPolicy]) -> str:
    """SHA-256 of the sorted matched policy ids joined by commas (of the empty string when none)."""
    joined = ",".join(sorted(str(m.policy_id) for m in matched))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
