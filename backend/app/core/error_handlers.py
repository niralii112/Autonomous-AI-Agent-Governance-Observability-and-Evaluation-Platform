"""Turn every failure into the one error body from the contract (ErrorResponse).

Nothing here ever returns a stack trace, SQL text or a secret. Unknown errors become a
plain INTERNAL_ERROR; the real cause is logged on the server.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.enums import ErrorCode
from app.core.exceptions import ERROR_HTTP_STATUS, AppError
from app.core.trace_context import current_trace_id  # noqa: F401  (re-exported)

logger = logging.getLogger("governance.errors")


def _details_to_list(details: Any) -> list[dict[str, str]] | None:
    """The contract wants details as a list of {field, message}. AppError may hold a dict."""
    if details is None:
        return None
    if isinstance(details, dict):
        return [{"field": str(k), "message": str(v)} for k, v in details.items()]
    return [{"field": str(d["field"]), "message": str(d["message"])} for d in details]


def error_response(
    status: int, code: ErrorCode, message: str, details: Any = None
) -> JSONResponse:
    body = {
        "error_code": code.value,
        "error_message": message,
        "details": _details_to_list(details),
        "trace_id": current_trace_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=status, content=body)


async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.http_status, exc.error_code, exc.error_message, exc.details)


async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part not in ("body", "query", "path")),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return error_response(
        ERROR_HTTP_STATUS[ErrorCode.VALIDATION_ERROR],
        ErrorCode.VALIDATION_ERROR,
        "Request body, query or path failed schema validation.",
        details,
    )


async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(404, ErrorCode.RESOURCE_NOT_FOUND, "Resource not found.")
    if exc.status_code == 405:
        return error_response(405, ErrorCode.VALIDATION_ERROR, "Method not allowed for this path.")
    logger.warning("Unexpected HTTP error %s", exc.status_code)
    return error_response(exc.status_code, ErrorCode.INTERNAL_ERROR, "The request could not be processed.")


async def handle_database_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Database unavailable: %s", type(exc).__name__)
    # Fail closed: the platform does nothing if it cannot reach PostgreSQL.
    return error_response(
        ERROR_HTTP_STATUS[ErrorCode.DATABASE_UNAVAILABLE],
        ErrorCode.DATABASE_UNAVAILABLE,
        "PostgreSQL unreachable; the platform fails closed.",
    )


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", type(exc).__name__)
    return error_response(500, ErrorCode.INTERNAL_ERROR, "An internal error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(OperationalError, handle_database_error)
    app.add_exception_handler(InterfaceError, handle_database_error)
    app.add_exception_handler(DBAPIError, handle_database_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
