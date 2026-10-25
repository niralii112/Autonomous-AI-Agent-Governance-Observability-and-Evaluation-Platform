import hashlib
import uuid

import pytest

from app.core.enums import PolicyEffect, PolicyOperator, PolicyResult
from app.schemas import MatchedPolicy, PolicyCondition, PolicyConditions
from app.services import policy_matching as pm

AGENT = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def ctx(payload=None, **kw):
    base = dict(action_type="FINANCE_PROPOSE_PAYMENT", agent_id=AGENT, agent_category="FINANCE",
                tool_name="payment_processor_sim", tool_sensitivity="WRITE", action_payload=payload or {})
    base.update(kw)
    return pm.EvalContext(**base)


def leaf(field, op, value=None):
    return PolicyCondition(field=field, operator=PolicyOperator(op), value=value)


def matches(field, op, value, payload=None, **kw):
    return pm.leaf_matches(leaf(field, op, value), ctx(payload, **kw))


def mp(key, effect, priority, mandatory=False, pid=None):
    return MatchedPolicy(policy_id=pid or uuid.uuid4(), policy_key=key, version=1, effect=PolicyEffect(effect),
                         priority=priority, is_mandatory=mandatory)


# ================================= operators =====================================================

@pytest.mark.parametrize("op,expected_value,actual,result", [
    ("EQ", "USD", "USD", True), ("EQ", "USD", "EUR", False),
    ("NEQ", "USD", "EUR", True), ("NEQ", "USD", "USD", False),
    ("IN", ["USD", "EUR"], "EUR", True), ("IN", ["USD", "EUR"], "GBP", False),
    ("NOT_IN", ["USD", "EUR"], "GBP", True), ("NOT_IN", ["USD", "EUR"], "USD", False),
])
def test_text_operators(op, expected_value, actual, result):
    assert matches("payload.currency", op, expected_value, {"currency": actual}) is result


@pytest.mark.parametrize("op,actual,result", [
    ("GT", 1000.01, True), ("GT", 1000, False), ("GT", 999, False),
    ("GTE", 1000, True), ("GTE", 999.99, False), ("GTE", 1001, True),
    ("LT", 999.99, True), ("LT", 1000, False),
    ("LTE", 1000, True), ("LTE", 1000.01, False), ("LTE", 0, True),
])
def test_numeric_operators_use_exact_boundaries(op, actual, result):
    assert matches("payload.amount", op, 1000, {"amount": actual}) is result


def test_ints_and_floats_compare_by_value():
    assert matches("payload.amount", "EQ", 100, {"amount": 100.0})
    assert matches("payload.amount", "IN", [1, 2, 100], {"amount": 100.0})


def test_exists():
    assert matches("payload.customer_id", "EXISTS", None, {"customer_id": "c-1"})
    assert not matches("payload.customer_id", "EXISTS", None, {"other": 1})
    assert matches("payload.flag", "EXISTS", None, {"flag": False})   # false is a value
    assert matches("payload.n", "EXISTS", None, {"n": 0})             # zero is a value
    assert matches("payload.s", "EXISTS", None, {"s": ""})            # empty text is a value


# ================================= missing and null ==============================================

@pytest.mark.parametrize("op,value", [("EQ", "x"), ("NEQ", "x"), ("IN", ["x"]), ("NOT_IN", ["x"]),
                                      ("GT", 1), ("GTE", 1), ("LT", 1), ("LTE", 1), ("EXISTS", None)])
def test_a_missing_payload_value_makes_every_operator_false(op, value):
    assert matches("payload.absent", op, value, {"other": 1}) is False


@pytest.mark.parametrize("op,value", [("EQ", "x"), ("NEQ", "x"), ("NOT_IN", ["x"]), ("EXISTS", None), ("GT", 1)])
def test_a_null_value_counts_as_missing(op, value):
    assert matches("payload.v", op, value, {"v": None}) is False


def test_missing_tool_sensitivity_is_missing_too():
    assert matches("tool_sensitivity", "EQ", "READ_ONLY", {}, tool_sensitivity=None) is False
    assert matches("tool_sensitivity", "NEQ", "READ_ONLY", {}, tool_sensitivity=None) is False


def test_a_path_through_something_that_is_not_an_object_is_missing():
    assert matches("payload.a.b", "EXISTS", None, {"a": "text"}) is False
    assert matches("payload.a.b", "EXISTS", None, {"a": [1, 2]}) is False


def test_nested_paths():
    assert matches("payload.customer.tier", "EQ", "gold", {"customer": {"tier": "gold"}})
    assert not matches("payload.customer.tier", "EQ", "gold", {"customer": {"tier": "silver"}})


# ================================= strict types ===================================================

@pytest.mark.parametrize("actual,expected,eq", [
    (True, 1, False), (1, True, False), (False, 0, False), (0, False, False),
    ("1", 1, False), (1, "1", False), ("true", True, False),
    (True, True, True), (False, False, True), ("1", "1", True),
])
def test_equality_never_mixes_types(actual, expected, eq):
    assert pm.same(actual, expected) is eq


def test_numeric_operators_on_non_numbers_are_false_not_errors():
    for bad in ("1500", True, [1], {"a": 1}):
        assert matches("payload.amount", "GT", 1000, {"amount": bad}) is False


def test_neq_is_true_when_the_types_differ_but_the_value_exists():
    assert matches("payload.amount", "NEQ", "100", {"amount": 100}) is True


def test_a_bool_in_the_payload_is_not_greater_than_a_number():
    assert matches("payload.flag", "GT", 0, {"flag": True}) is False


# ================================= top-level fields ===============================================

def test_top_level_fields():
    assert matches("action_type", "EQ", "FINANCE_PROPOSE_PAYMENT")
    assert matches("agent_category", "IN", ["FINANCE", "CUSTOMER_SUPPORT"])
    assert matches("tool_name", "EQ", "payment_processor_sim")
    assert matches("tool_sensitivity", "EQ", "WRITE")
    assert matches("agent_id", "EQ", AGENT)
    assert not matches("agent_id", "EQ", "00000000-0000-4000-8000-000000000000")


# ================================= malformed conditions fail closed ===============================

@pytest.mark.parametrize("field,op,value", [
    ("password", "EQ", "x"),            # not on the allow-list
    ("__class__", "EQ", "x"),
    ("payload.amount", "GT", "lots"),    # wrong value type
    ("action_type", "EQ", "MAKE_COFFEE"),
    ("payload.x", "IN", []),
])
def test_malformed_leaves_raise(field, op, value):
    with pytest.raises(ValueError):
        pm.leaf_matches(PolicyCondition.model_construct(field=field, operator=PolicyOperator(op), value=value), ctx())


def test_empty_conditions_raise():
    with pytest.raises(ValueError):
        pm.conditions_match(PolicyConditions(all=[], any=[]), ctx())


# ================================= all / any ======================================================

def test_all_needs_every_leaf():
    c = PolicyConditions(all=[leaf("payload.amount", "GT", 100), leaf("payload.currency", "EQ", "USD")], any=[])
    assert pm.conditions_match(c, ctx({"amount": 200, "currency": "USD"}))
    assert not pm.conditions_match(c, ctx({"amount": 200, "currency": "EUR"}))
    assert not pm.conditions_match(c, ctx({"amount": 50, "currency": "USD"}))


def test_any_needs_at_least_one_leaf():
    c = PolicyConditions(all=[], any=[leaf("payload.a", "EQ", 1), leaf("payload.b", "EQ", 2)])
    assert pm.conditions_match(c, ctx({"a": 1})) and pm.conditions_match(c, ctx({"b": 2}))
    assert not pm.conditions_match(c, ctx({"a": 9, "b": 9}))


def test_all_and_any_together():
    c = PolicyConditions(all=[leaf("action_type", "EQ", "FINANCE_PROPOSE_PAYMENT")],
                         any=[leaf("payload.amount", "GT", 1000), leaf("payload.payee_id", "EQ", "bad")])
    assert pm.conditions_match(c, ctx({"amount": 5000}))
    assert pm.conditions_match(c, ctx({"amount": 1, "payee_id": "bad"}))
    assert not pm.conditions_match(c, ctx({"amount": 1, "payee_id": "good"}))
    assert not pm.conditions_match(c, ctx({"amount": 5000}, action_type="SUPPORT_PROPOSE_REFUND"))


def test_a_later_malformed_leaf_is_still_found_even_if_an_earlier_leaf_is_false():
    # `all()` stops at the first false leaf; the engine must not hide a broken policy behind it
    bad = PolicyCondition.model_construct(field="password", operator=PolicyOperator.EQ, value="x")
    c = PolicyConditions.model_construct(all=[leaf("payload.amount", "GT", 10 ** 9), bad], any=[])
    with pytest.raises(ValueError):
        pm.conditions_match(c, ctx({"amount": 1}))


# ================================= scope ==========================================================

@pytest.mark.parametrize("scope,applies", [
    ((None, None, None), True),
    ((uuid.UUID(AGENT), None, None), True),
    ((uuid.uuid4(), None, None), False),
    ((None, "FINANCE", None), True),
    ((None, "CUSTOMER_SUPPORT", None), False),
    ((None, None, "FINANCE_PROPOSE_PAYMENT"), True),
    ((None, None, "SUPPORT_PROPOSE_REFUND"), False),
    ((uuid.UUID(AGENT), "FINANCE", "FINANCE_PROPOSE_PAYMENT"), True),
    ((uuid.UUID(AGENT), "FINANCE", "SUPPORT_PROPOSE_REFUND"), False),   # every non-null scope must match
])
def test_scope(scope, applies):
    assert pm.scope_applies(*scope, ctx()) is applies


# ================================= choosing the winner ============================================

def test_no_match():
    assert pm.choose_winner([]) == (PolicyResult.NO_MATCH, None)


def test_single_match_decides():
    m = mp("a", "ALLOW", 100)
    assert pm.choose_winner([m]) == (PolicyResult.ALLOW, m)


def test_mandatory_block_beats_a_higher_precedence_allow():
    allow, block = mp("allow-it", "ALLOW", 1), mp("block-it", "BLOCK", 900, mandatory=True)
    assert pm.choose_winner([allow, block]) == (PolicyResult.BLOCK, block)


def test_among_mandatory_blocks_the_lowest_priority_number_wins_then_the_key():
    a, b, c = mp("zeta", "BLOCK", 10, True), mp("alpha", "BLOCK", 20, True), mp("beta", "BLOCK", 10, True)
    assert pm.choose_winner([a, b, c])[1] is c  # priority 10 twice; "beta" < "zeta"


def test_a_non_mandatory_block_can_lose_to_a_higher_precedence_allow():
    allow, block = mp("allow-it", "ALLOW", 5), mp("block-it", "BLOCK", 50)
    assert pm.choose_winner([block, allow]) == (PolicyResult.ALLOW, allow)


def test_lowest_priority_number_group_decides_not_the_whole_set():
    review, allow = mp("review-it", "HUMAN_REVIEW", 60), mp("allow-it", "ALLOW", 100)
    assert pm.choose_winner([allow, review])[0] == PolicyResult.HUMAN_REVIEW


def test_within_one_priority_the_most_restrictive_effect_wins():
    allow, review, block = mp("a-allow", "ALLOW", 50), mp("b-review", "HUMAN_REVIEW", 50), mp("c-block", "BLOCK", 50)
    assert pm.choose_winner([allow, review])[0] == PolicyResult.HUMAN_REVIEW
    assert pm.choose_winner([allow, review, block])[0] == PolicyResult.BLOCK


def test_ties_go_to_the_lowest_policy_key():
    first, second = mp("alpha-review", "HUMAN_REVIEW", 60), mp("zulu-review", "HUMAN_REVIEW", 60)
    assert pm.choose_winner([second, first])[1] is first


def test_input_order_never_changes_the_outcome():
    items = [mp("a", "ALLOW", 100), mp("b", "HUMAN_REVIEW", 60), mp("c", "HUMAN_REVIEW", 60), mp("d", "BLOCK", 70)]
    expected = pm.choose_winner(items)[1].policy_key
    for rotation in range(len(items)):
        assert pm.choose_winner(items[rotation:] + items[:rotation])[1].policy_key == expected


def test_the_most_restrictive_wins_even_at_a_lower_priority_number_for_review_over_block():
    # review has precedence (60) over a non-mandatory block (70): the block is ignored
    review, block = mp("review-it", "HUMAN_REVIEW", 60), mp("block-it", "BLOCK", 70)
    assert pm.choose_winner([review, block])[0] == PolicyResult.HUMAN_REVIEW


# ================================= conflict and snapshot hash =====================================

def test_conflict_means_more_than_one_distinct_effect():
    assert pm.conflict_detected([]) is False
    assert pm.conflict_detected([mp("a", "ALLOW", 1), mp("b", "ALLOW", 2)]) is False
    assert pm.conflict_detected([mp("a", "ALLOW", 1), mp("b", "BLOCK", 2)]) is True


def test_snapshot_hash_is_sha256_of_sorted_ids_joined_by_commas():
    one, two = uuid.UUID("00000000-0000-4000-8000-000000000002"), uuid.UUID("00000000-0000-4000-8000-000000000001")
    items = [mp("a", "ALLOW", 1, pid=one), mp("b", "ALLOW", 2, pid=two)]
    expected = hashlib.sha256(f"{two},{one}".encode()).hexdigest()
    assert pm.snapshot_hash(items) == pm.snapshot_hash(list(reversed(items))) == expected


def test_snapshot_hash_for_no_match_is_the_hash_of_the_empty_string():
    assert pm.snapshot_hash([]) == hashlib.sha256(b"").hexdigest()
