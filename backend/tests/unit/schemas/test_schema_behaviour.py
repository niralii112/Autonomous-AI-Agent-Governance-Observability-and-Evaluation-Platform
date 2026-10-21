from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import ActionType, SortOrder, UserRole
from app.schemas import (
    ACTION_PAYLOAD_MODELS,
    ErrorResponse,
    FinanceProposePaymentPayload,
    LoginRequest,
    Page,
    PaginationParams,
    PolicyConditions,
    RiskContext,
    TokenResponse,
    UserResponse,
)

NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def user_dict():
    return {
        "user_id": uuid4(), "username": "nirali", "email": "n@example.com", "role": "ADMIN",
        "is_active": True, "created_at": NOW, "updated_at": NOW, "last_login_at": None,
    }


# --- auth ---
def test_login_request_valid():
    assert LoginRequest(username="a", password="b").username == "a"


@pytest.mark.parametrize("bad", [{"username": "", "password": "x"}, {"username": "a", "password": ""},
                                 {"username": "a" * 65, "password": "x"}, {"username": "a"}])
def test_login_request_rejects_bad_input(bad):
    with pytest.raises(ValidationError):
        LoginRequest(**bad)


def test_login_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="a", password="b", admin=True)


def test_token_type_must_be_bearer():
    ok = TokenResponse(access_token="t", token_type="bearer", expires_in=3600, user=user_dict())
    assert ok.user.role == UserRole.ADMIN
    with pytest.raises(ValidationError):
        TokenResponse(access_token="t", token_type="basic", expires_in=3600, user=user_dict())


def test_user_response_never_has_a_password_field():
    assert "password_hash" not in UserResponse.model_fields
    assert "password" not in UserResponse.model_fields


def test_user_response_can_be_built_from_an_orm_like_object():
    orm_row = SimpleNamespace(**user_dict(), password_hash="secret")
    out = UserResponse.model_validate(orm_row)
    assert out.username == "nirali"
    assert "password_hash" not in out.model_dump()


# --- pagination and pages ---
def test_pagination_defaults():
    p = PaginationParams()
    assert (p.page, p.page_size, p.sort_by, p.sort_order) == (1, 25, "created_at", SortOrder.desc)


@pytest.mark.parametrize("kw", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"sort_order": "up"}])
def test_pagination_rejects_out_of_range(kw):
    with pytest.raises(ValidationError):
        PaginationParams(**kw)


def test_generic_page():
    page = Page[int](items=[1, 2], page=1, page_size=25, total_items=2, total_pages=1)
    assert page.items == [1, 2]
    with pytest.raises(ValidationError):
        Page[int](items=[], page=1, page_size=101, total_items=0, total_pages=0)


# --- errors ---
def test_error_response_fields():
    assert {"error_code", "error_message"} <= set(ErrorResponse.model_fields)


# --- risk context (shared with Student 2) ---
def ctx(**kw):
    base = dict(recent_blocked_count_24h=0, recent_failed_count_24h=0, agent_trust_tier=2, submitted_at=NOW)
    return RiskContext(**{**base, **kw})


def test_risk_context_ok():
    assert ctx().agent_trust_tier == 2


@pytest.mark.parametrize("kw", [{"agent_trust_tier": 0}, {"agent_trust_tier": 4},
                                {"recent_blocked_count_24h": -1}])
def test_risk_context_limits(kw):
    with pytest.raises(ValidationError):
        ctx(**kw)


# --- policy conditions ---
def test_policy_conditions_default_to_empty_lists_not_shared():
    a, b = PolicyConditions(), PolicyConditions()
    a.all.append(object())  # must not leak into b
    assert b.all == [] and b.any == []


# --- action payloads ---
def test_every_action_type_has_a_payload_model():
    assert set(ACTION_PAYLOAD_MODELS) == set(ActionType)
    assert ACTION_PAYLOAD_MODELS[ActionType.FINANCE_PROPOSE_PAYMENT] is FinanceProposePaymentPayload


def pay(**kw):
    return {**dict(payee_id="p1", amount=100.5, currency="USD", reference="inv-1"), **kw}


def test_payment_payload_valid():
    assert FinanceProposePaymentPayload(**pay()).amount == 100.5


@pytest.mark.parametrize("kw", [{"amount": 0}, {"amount": 0.001}, {"amount": 100000001},
                               {"currency": "US"}, {"currency": "USDX"}, {"payee_id": ""}])
def test_payment_payload_limits(kw):
    with pytest.raises(ValidationError):
        FinanceProposePaymentPayload(**pay(**kw))


def test_payment_payload_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        FinanceProposePaymentPayload(**pay(), extra_field=1)


def test_payment_payload_requires_all_fields():
    with pytest.raises(ValidationError):
        FinanceProposePaymentPayload(payee_id="p1", amount=5)
