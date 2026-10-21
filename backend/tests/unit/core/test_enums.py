from app.core import enums
from app.core.enums import (
    ActionType,
    AgentCategory,
    ApprovalStatus,
    ErrorCode,
    GovernanceDecision,
    PolicyResult,
    SortOrder,
    ToolSensitivity,
)


def values(enum_cls):
    return [m.value for m in enum_cls]


def test_governance_decision_values():
    assert values(GovernanceDecision) == ["ALLOW", "HUMAN_REVIEW", "BLOCK"]


def test_policy_result_adds_no_match_and_error():
    assert values(PolicyResult) == ["ALLOW", "HUMAN_REVIEW", "BLOCK", "NO_MATCH", "ERROR"]


def test_approval_status_values():
    assert values(ApprovalStatus) == ["PENDING", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED"]


def test_tool_sensitivity_values():
    assert values(ToolSensitivity) == ["READ_ONLY", "SENSITIVE_READ", "WRITE", "PRIVILEGED"]


def test_agent_category_values():
    assert values(AgentCategory) == ["FINANCE", "CUSTOMER_SUPPORT", "IT_OPERATIONS"]


def test_action_type_has_the_12_spec_values():
    assert len(ActionType) == 12
    assert ActionType.FINANCE_PROPOSE_PAYMENT.value == "FINANCE_PROPOSE_PAYMENT"
    assert ActionType.SUPPORT_PROPOSE_REFUND.value == "SUPPORT_PROPOSE_REFUND"


def test_sort_order_is_lowercase_exception():
    assert values(SortOrder) == ["asc", "desc"]


def test_error_code_count_matches_spec_table():
    assert len(ErrorCode) == 29


def test_audit_event_count_matches_spec_list():
    assert len(enums.AuditEventName) == 35


def test_every_enum_value_is_upper_snake_except_sort_order():
    for name in dir(enums):
        obj = getattr(enums, name)
        if isinstance(obj, type) and issubclass(obj, enums.Enum) and obj is not enums.Enum:
            if obj is SortOrder:
                continue
            for member in obj:
                assert member.value == member.name
                assert member.value.isupper()


def test_enums_compare_equal_to_plain_strings():
    # str-based enums serialise to plain JSON strings
    assert GovernanceDecision.BLOCK == "BLOCK"
