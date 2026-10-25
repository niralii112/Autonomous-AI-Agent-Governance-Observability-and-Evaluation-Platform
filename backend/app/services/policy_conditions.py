"""Validation of the policy condition language (spec 13.1).

A policy matches when EVERY leaf in `all` is true AND (`any` is empty OR at least one leaf in
`any` is true). A leaf is {field, operator, value}.

Allowed fields: action_type, agent_id, agent_category, tool_name, tool_sensitivity, or
payload.<key> (a dot path into action_payload). This is the allow-list: nothing else can be
used in a condition.
"""

import re
import uuid
from typing import Any

from app.core.enums import (
    ActionType, AgentCategory, ErrorCode, PolicyOperator, ToolSensitivity,
)
from app.core.exceptions import AppError
from app.schemas import PolicyCondition, PolicyConditions

TOP_LEVEL_FIELDS = {"action_type", "agent_id", "agent_category", "tool_name", "tool_sensitivity"}
PAYLOAD_FIELD = re.compile(r"^payload\.[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")
ENUM_FIELDS: dict[str, type] = {
    "action_type": ActionType, "agent_category": AgentCategory, "tool_sensitivity": ToolSensitivity,
}
SET_OPERATORS = {PolicyOperator.IN, PolicyOperator.NOT_IN}
EQUALITY_OPERATORS = {PolicyOperator.EQ, PolicyOperator.NEQ}
NUMERIC_OPERATORS = {PolicyOperator.GT, PolicyOperator.GTE, PolicyOperator.LT, PolicyOperator.LTE}
MAX_LIST_ITEMS = 100


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_enum_value(field: str, value: Any) -> str | None:
    enum_cls = ENUM_FIELDS[field]
    if not isinstance(value, str) or value not in {m.value for m in enum_cls}:
        return f"{value!r} is not a valid {enum_cls.__name__}"
    return None


def check_leaf(leaf: PolicyCondition) -> str | None:
    """Return an error message for one leaf, or None if it is valid."""
    field, op, value = leaf.field, leaf.operator, leaf.value
    is_payload = bool(PAYLOAD_FIELD.match(field))
    if field not in TOP_LEVEL_FIELDS and not is_payload:
        return (f"unknown field {field!r}; allowed: {', '.join(sorted(TOP_LEVEL_FIELDS))} "
                "or payload.<key>")

    if op == PolicyOperator.EXISTS:
        if not is_payload:
            return "EXISTS can only be used on payload fields"
        return None if value is None else "EXISTS takes no value"

    if op in NUMERIC_OPERATORS:
        if not is_payload:
            return f"{op.value} can only be used on payload fields"
        return None if _is_number(value) else f"{op.value} needs a number"

    if op in SET_OPERATORS:
        if not isinstance(value, list) or not value:
            return f"{op.value} needs a non-empty list"
        if len(value) > MAX_LIST_ITEMS:
            return f"{op.value} list may have at most {MAX_LIST_ITEMS} items"
        if not all(_is_scalar(v) for v in value):
            return f"{op.value} list items must be strings, numbers or booleans"
        items = value
    else:  # EQ / NEQ
        if not _is_scalar(value):
            return f"{op.value} needs a single string, number or boolean"
        items = [value]

    if field in ENUM_FIELDS:
        for item in items:
            problem = _check_enum_value(field, item)
            if problem:
                return problem
    if field == "agent_id":
        for item in items:
            try:
                uuid.UUID(str(item))
            except ValueError:
                return f"{item!r} is not a valid UUID"
    if field in ("tool_name", "agent_id") and not all(isinstance(i, str) for i in items):
        return f"{field} values must be strings"
    return None


def validate_conditions(conditions: PolicyConditions) -> None:
    """Raise AppError(VALIDATION_ERROR) listing every problem found."""
    problems: dict[str, str] = {}
    if not conditions.all and not conditions.any:
        problems["conditions"] = "at least one of 'all' or 'any' must contain a condition"
    for group_name, leaves in (("all", conditions.all), ("any", conditions.any)):
        for index, leaf in enumerate(leaves):
            message = check_leaf(leaf)
            if message:
                problems[f"conditions.{group_name}[{index}]"] = message
    if problems:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Policy conditions failed validation.", problems)
