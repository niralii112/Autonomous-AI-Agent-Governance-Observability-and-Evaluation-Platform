import logging

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from opentelemetry.sdk.trace import TracerProvider
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError

from app.core.enums import ErrorCode
from app.core.error_handlers import current_trace_id, register_error_handlers
from app.core.exceptions import AppError, NotFoundError
from app.schemas import ErrorResponse


class Body(BaseModel):
    amount: float = Field(gt=0)
    nested: dict | None = None


def build_app():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/app-error")
    async def app_error():
        raise AppError(ErrorCode.SELF_APPROVAL_FORBIDDEN, "You cannot approve your own action.")

    @app.get("/app-error-details")
    async def app_error_details():
        raise AppError(ErrorCode.INVALID_ACTION_PAYLOAD, "bad", {"amount": "must be positive"})

    @app.get("/not-found")
    async def not_found():
        raise NotFoundError("Agent 42 not found.")

    @app.post("/validate")
    async def validate(body: Body):
        return {"ok": True}

    @app.get("/query")
    async def query(page: int):
        return {"page": page}

    @app.get("/db-down")
    async def db_down():
        raise OperationalError("SELECT secret_table", {}, Exception("password=hunter2 host=10.0.0.5"))

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail: /etc/passwd")

    @app.get("/http-418")
    async def teapot():
        raise HTTPException(status_code=418, detail="short and stout")

    return app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def check_shape(response):
    """Every error body must be a valid ErrorResponse from the contract."""
    return ErrorResponse.model_validate(response.json())


async def test_app_error_uses_its_code_and_status(client):
    r = await client.get("/app-error")
    assert r.status_code == 403
    body = check_shape(r)
    assert body.error_code == ErrorCode.SELF_APPROVAL_FORBIDDEN
    assert body.error_message == "You cannot approve your own action."
    assert body.details is None


async def test_dict_details_become_a_list_of_field_message(client):
    r = await client.get("/app-error-details")
    assert r.status_code == 422
    assert r.json()["details"] == [{"field": "amount", "message": "must be positive"}]


async def test_not_found_subclass(client):
    r = await client.get("/not-found")
    assert r.status_code == 404 and r.json()["error_code"] == "RESOURCE_NOT_FOUND"


async def test_unknown_route_is_resource_not_found(client):
    r = await client.get("/no-such-route")
    assert r.status_code == 404
    assert check_shape(r).error_code == ErrorCode.RESOURCE_NOT_FOUND


async def test_wrong_method_is_405_validation_error(client):
    r = await client.delete("/app-error")
    assert r.status_code == 405
    assert check_shape(r).error_code == ErrorCode.VALIDATION_ERROR


async def test_body_validation_error_lists_fields(client):
    r = await client.post("/validate", json={"amount": -5})
    assert r.status_code == 422
    body = check_shape(r)
    assert body.error_code == ErrorCode.VALIDATION_ERROR
    assert body.details and body.details[0].field == "amount"


async def test_query_validation_error(client):
    r = await client.get("/query", params={"page": "abc"})
    assert r.status_code == 422
    assert r.json()["details"][0]["field"] == "page"


async def test_database_errors_are_503_and_leak_nothing(client):
    r = await client.get("/db-down")
    assert r.status_code == 503
    assert check_shape(r).error_code == ErrorCode.DATABASE_UNAVAILABLE
    text = r.text
    assert "hunter2" not in text and "10.0.0.5" not in text and "secret_table" not in text


async def test_unexpected_error_is_500_and_leaks_nothing(client, caplog):
    with caplog.at_level(logging.ERROR, logger="governance.errors"):
        r = await client.get("/boom")
    assert r.status_code == 500
    assert check_shape(r).error_code == ErrorCode.INTERNAL_ERROR
    assert "etc/passwd" not in r.text and "RuntimeError" not in r.text
    assert any("RuntimeError" in rec.getMessage() for rec in caplog.records)  # logged on the server


async def test_other_http_errors_become_internal_error_shape(client):
    r = await client.get("/http-418")
    assert r.status_code == 418
    body = check_shape(r)
    assert "stout" not in r.text and body.error_code == ErrorCode.INTERNAL_ERROR


async def test_trace_id_is_none_without_a_span(client):
    assert (await client.get("/app-error")).json()["trace_id"] is None


def test_trace_id_is_32_lowercase_hex_with_an_active_span():
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("x"):
        tid = current_trace_id()
    assert tid is not None and len(tid) == 32 and tid == tid.lower()
    int(tid, 16)


async def test_timestamp_is_present_and_parseable(client):
    body = check_shape(await client.get("/app-error"))
    assert body.timestamp.tzinfo is not None
