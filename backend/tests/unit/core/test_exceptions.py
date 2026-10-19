import pytest

from app.core.enums import ErrorCode
from app.core.exceptions import (
    ERROR_HTTP_STATUS,
    AppError,
    AuthenticationError,
    AuthorizationError,
    DuplicateResourceError,
    NotFoundError,
)


def test_every_error_code_has_an_http_status():
    assert set(ERROR_HTTP_STATUS) == set(ErrorCode)


@pytest.mark.parametrize(
    "code,status",
    [
        (ErrorCode.AUTH_MISSING_CREDENTIALS, 401),
        (ErrorCode.AUTH_INSUFFICIENT_ROLE, 403),
        (ErrorCode.SELF_APPROVAL_FORBIDDEN, 403),
        (ErrorCode.VALIDATION_ERROR, 422),
        (ErrorCode.AGENT_NOT_REGISTERED, 404),
        (ErrorCode.DUPLICATE_RESOURCE, 409),
        (ErrorCode.APPROVAL_ALREADY_CONSUMED, 409),
        (ErrorCode.POLICY_REVALIDATION_FAILED, 409),
        (ErrorCode.DATABASE_UNAVAILABLE, 503),
        (ErrorCode.POLICY_ENGINE_FAILURE, 500),
        (ErrorCode.DIRECT_EXECUTION_FORBIDDEN, 500),
    ],
)
def test_http_status_matches_spec(code, status):
    assert AppError(code, "x").http_status == status


def test_app_error_keeps_fields():
    err = AppError(ErrorCode.INVALID_ACTION_PAYLOAD, "bad payload", {"field": "amount"})
    assert err.error_code == ErrorCode.INVALID_ACTION_PAYLOAD
    assert err.error_message == "bad payload"
    assert err.details == {"field": "amount"}
    assert str(err) == "bad payload"


def test_details_default_is_none():
    assert AppError(ErrorCode.INTERNAL_ERROR, "boom").details is None


def test_subclasses_are_app_errors_with_default_codes():
    assert NotFoundError().error_code == ErrorCode.RESOURCE_NOT_FOUND
    assert NotFoundError(error_code=ErrorCode.AGENT_NOT_REGISTERED).http_status == 404
    assert DuplicateResourceError().http_status == 409
    assert AuthenticationError().error_code == ErrorCode.AUTH_INVALID_CREDENTIALS
    assert AuthorizationError().http_status == 403
    assert isinstance(NotFoundError(), AppError)
