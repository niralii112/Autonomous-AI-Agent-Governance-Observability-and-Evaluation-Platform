"""Application errors (spec section 9.5).

Every error the API returns has one shape: error_code, error_message, details.
Raise AppError (or a subclass) anywhere; core/error_handlers.py will turn it
into the standard error body later.
"""

from typing import Any

from app.core.enums import ErrorCode

# HTTP status for every error code, exactly as in the spec table.
ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_MISSING_CREDENTIALS: 401,
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_INSUFFICIENT_ROLE: 403,
    ErrorCode.SELF_APPROVAL_FORBIDDEN: 403,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.INVALID_ACTION_PAYLOAD: 422,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.AGENT_NOT_REGISTERED: 404,
    ErrorCode.TRACE_NOT_FOUND: 404,
    ErrorCode.DUPLICATE_RESOURCE: 409,
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: 409,
    ErrorCode.APPROVAL_NOT_PENDING: 409,
    ErrorCode.APPROVAL_EXPIRED: 409,
    ErrorCode.APPROVAL_ALREADY_CONSUMED: 409,
    ErrorCode.INVALID_STATE_TRANSITION: 409,
    ErrorCode.EXECUTION_RETRY_NOT_ALLOWED: 409,
    ErrorCode.DATABASE_UNAVAILABLE: 503,
    ErrorCode.TELEMETRY_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.POLICY_ENGINE_FAILURE: 500,
    ErrorCode.TOOL_EXECUTION_FAILED: 500,
    ErrorCode.TOOL_EXECUTION_TIMEOUT: 500,
    ErrorCode.TOOL_NOT_AVAILABLE: 500,
    ErrorCode.POLICY_REVALIDATION_FAILED: 409,
    ErrorCode.EXECUTION_RESULT_UNRECORDED: 500,
    ErrorCode.EXECUTION_GRANT_INVALID: 500,
    ErrorCode.DIRECT_EXECUTION_FORBIDDEN: 500,
}


class AppError(Exception):
    """Base class for all expected application errors."""

    def __init__(
        self,
        error_code: ErrorCode,
        error_message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message
        self.details = details

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS[self.error_code]


class NotFoundError(AppError):
    def __init__(
        self,
        error_message: str = "Resource not found.",
        details: dict[str, Any] | None = None,
        error_code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
    ) -> None:
        super().__init__(error_code, error_message, details)


class DuplicateResourceError(AppError):
    def __init__(
        self,
        error_message: str = "A resource with these unique values already exists.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ErrorCode.DUPLICATE_RESOURCE, error_message, details)


class AuthenticationError(AppError):
    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.AUTH_INVALID_CREDENTIALS,
        error_message: str = "Authentication failed.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error_code, error_message, details)


class AuthorizationError(AppError):
    def __init__(
        self,
        error_message: str = "Your role is not allowed to do this.",
        details: dict[str, Any] | None = None,
        error_code: ErrorCode = ErrorCode.AUTH_INSUFFICIENT_ROLE,
    ) -> None:
        super().__init__(error_code, error_message, details)
