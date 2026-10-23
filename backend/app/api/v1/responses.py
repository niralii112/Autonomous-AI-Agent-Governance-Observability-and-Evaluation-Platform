"""Shared OpenAPI response descriptions so /docs shows the real error format."""

from app.schemas import ErrorResponse


def errors(*codes: int) -> dict[int | str, dict]:
    return {code: {"model": ErrorResponse} for code in codes}
