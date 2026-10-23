"""Student 3 Jaeger query-client boundary.

Master specification v1.0.0:
- Section 12.17: canonical fetch_trace signature
- Section 9.8: Jaeger environment configuration
- Section 16.3: verify Jaeger query API against pinned image
- Section 16.4: telemetry failure must not expose fake data

Jaeger HTTP endpoint and JSON decoding are intentionally NOT
implemented until the pinned image version has been verified.
"""

from __future__ import annotations

import os
import re
from typing import Any


_TRACE_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")

_DEFAULT_JAEGER_QUERY_URL = "http://localhost:16686"
_DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0


class TraceQueryUnavailable(Exception):
    """Internal adapter error for unavailable telemetry."""


def _validate_trace_id(trace_id: str) -> None:
    """Reject IDs that are not OpenTelemetry trace identifiers."""
    if (
        not isinstance(trace_id, str)
        or _TRACE_ID_PATTERN.fullmatch(trace_id) is None
    ):
        raise ValueError(
            "trace_id must contain exactly 32 lowercase hex characters"
        )


def _query_settings() -> tuple[str, float]:
    """Read the approved Jaeger query configuration.

    Uses standard-library environment access only.
    Student 1's Settings object remains the integration authority.
    """
    url = os.environ.get(
        "JAEGER_QUERY_URL",
        _DEFAULT_JAEGER_QUERY_URL,
    ).strip()

    if not url or not (
        url.startswith("http://")
        or url.startswith("https://")
    ):
        raise TraceQueryUnavailable(
            "Jaeger query URL is not configured correctly"
        )

    raw_timeout = os.environ.get(
        "TELEMETRY_QUERY_TIMEOUT_SECONDS",
        str(_DEFAULT_QUERY_TIMEOUT_SECONDS),
    )

    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise TraceQueryUnavailable(
            "Telemetry query timeout is invalid"
        ) from exc

    if not (0 < timeout <= 300):
        raise TraceQueryUnavailable(
            "Telemetry query timeout is outside the supported range"
        )

    return url.rstrip("/"), timeout


async def fetch_trace(trace_id: str) -> dict[str, Any]:
    """Canonical raw trace adapter interface.

    This boundary intentionally fails closed until the pinned Jaeger
    image and its query API have been verified.

    The service layer must translate TraceQueryUnavailable into
    the canonical TELEMETRY_UNAVAILABLE application error.
    """
    _validate_trace_id(trace_id)
    _query_settings()

    raise TraceQueryUnavailable(
        "Jaeger query adapter is awaiting pinned-version verification"
    )
