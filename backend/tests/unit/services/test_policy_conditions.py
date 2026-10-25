import pytest

from app.core.enums import ErrorCode, PolicyOperator
from app.core.exceptions import AppError
from app.schemas import PolicyCondition, PolicyConditions
from app.services.policy_conditions import check_leaf, validate_conditions


def leaf(field, op, value=None):
    return PolicyCondition(field=field, operator=PolicyOperator(op), value=value)


def conditions(all_=(), any_=()):
    return PolicyConditions(all=list(all_), any=list(any_))


# ---- valid leaves -----------------------------------------------------------------------------

@pytest.mark.parametrize("field,op,value", [
    ("action_type", "EQ", "FINANCE_PROPOSE_PAYMENT"),
    ("action_type", "IN", ["FINANCE_PROPOSE_PAYMENT", "SUPPORT_PROPOSE_REFUND"]),
    ("action_type", "NEQ", "FINANCE_GET_REPORT"),
    ("agent_category", "EQ", "FINANCE"),
    ("agent_category", "NOT_IN", ["CUSTOMER_SUPPORT"]),
    ("tool_sensitivity", "EQ", "READ_ONLY"),
    ("tool_name", "EQ", "payment_processor_sim"),
    ("tool_name", "IN", ["a", "b"]),
    ("agent_id", "EQ", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
    ("payload.amount", "GT", 1000),
    ("payload.amount", "GTE", 0.5),
    ("payload.amount", "LT", 5),
    ("payload.amount", "LTE", 1000),
    ("payload.payee_id", "IN", ["payee-1", "payee-2"]),
    ("payload.payee_id", "NOT_IN", ["payee-1"]),
    ("payload.currency", "EQ", "USD"),
    ("payload.flag", "EQ", True),
    ("payload.nested.deep.key", "EQ", "x"),
    ("payload.customer_id", "EXISTS", None),
])
def test_valid_leaves(field, op, value):
    assert check_leaf(leaf(field, op, value)) is None


# ---- invalid leaves ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["amount", "payload", "payload.", "payload..x", "payload.a b", "payload.a-b",
                                   "Action_Type", "action_payload.amount", "user_id", "__class__", "payload.x;DROP"])
def test_fields_outside_the_allow_list_are_rejected(field):
    assert "unknown field" in check_leaf(leaf(field, "EQ", "x"))


@pytest.mark.parametrize("field,op,value,fragment", [
    ("action_type", "EQ", "MAKE_COFFEE", "not a valid ActionType"),
    ("action_type", "IN", ["FINANCE_GET_REPORT", "NOPE"], "not a valid ActionType"),
    ("agent_category", "EQ", "PIRATE", "not a valid AgentCategory"),
    ("tool_sensitivity", "EQ", "TOP_SECRET", "not a valid ToolSensitivity"),
    ("action_type", "EQ", 5, "not a valid ActionType"),
    ("agent_id", "EQ", "not-a-uuid", "not a valid UUID"),
    ("agent_id", "IN", ["3fa85f64-5717-4562-b3fc-2c963f66afa6", "nope"], "not a valid UUID"),
    ("tool_name", "EQ", 12, "must be strings"),
])
def test_wrong_values_for_known_fields(field, op, value, fragment):
    assert fragment in check_leaf(leaf(field, op, value))


@pytest.mark.parametrize("field,op", [("action_type", "GT"), ("tool_name", "LTE"), ("agent_category", "LT"), ("agent_id", "GTE")])
def test_numeric_operators_only_on_payload_fields(field, op):
    assert "only be used on payload fields" in check_leaf(leaf(field, op, 5))


@pytest.mark.parametrize("op,value", [("GT", "100"), ("GTE", True), ("LT", None), ("LTE", [1]), ("GT", {"a": 1})])
def test_numeric_operators_need_a_number(op, value):
    assert "needs a number" in check_leaf(leaf("payload.amount", op, value))


@pytest.mark.parametrize("op,value", [("IN", "a"), ("IN", []), ("NOT_IN", None), ("IN", [[1]]), ("IN", [{"a": 1}]), ("IN", [None])])
def test_set_operators_need_a_flat_non_empty_list(op, value):
    assert check_leaf(leaf("payload.x", op, value)) is not None


def test_set_operator_list_size_is_limited():
    assert "at most 100" in check_leaf(leaf("payload.x", "IN", list(range(101))))
    assert check_leaf(leaf("payload.x", "IN", list(range(100)))) is None


@pytest.mark.parametrize("op,value", [("EQ", None), ("NEQ", [1]), ("EQ", {"a": 1})])
def test_equality_needs_one_scalar(op, value):
    assert "single string, number or boolean" in check_leaf(leaf("payload.x", op, value))


def test_exists_only_on_payload_fields_and_takes_no_value():
    assert "only be used on payload" in check_leaf(leaf("action_type", "EXISTS"))
    assert check_leaf(leaf("payload.x", "EXISTS", True)) == "EXISTS takes no value"


# ---- whole condition set ----------------------------------------------------------------------

def test_empty_conditions_are_rejected():
    with pytest.raises(AppError) as e:
        validate_conditions(conditions())
    assert e.value.error_code == ErrorCode.VALIDATION_ERROR and "conditions" in e.value.details


def test_only_any_is_enough():
    validate_conditions(conditions(any_=[leaf("tool_sensitivity", "EQ", "WRITE")]))


def test_all_problems_are_reported_at_once_with_their_position():
    with pytest.raises(AppError) as e:
        validate_conditions(conditions(
            all_=[leaf("action_type", "EQ", "FINANCE_GET_REPORT"), leaf("nonsense", "EQ", 1)],
            any_=[leaf("payload.x", "GT", "high")]))
    assert set(e.value.details) == {"conditions.all[1]", "conditions.any[0]"}
    assert e.value.http_status == 422


def test_the_seed_policies_all_pass_validation():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("seed_for_conditions", path)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    assert len(seed.SEED_POLICIES) == 10
    for item in seed.SEED_POLICIES:
        validate_conditions(PolicyConditions.model_validate(item["conditions"]))
