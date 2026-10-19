"""Payload hashing (spec section 9.2, payload_hash)."""

import hashlib
import json
from typing import Any


def compute_payload_hash(action_payload: dict[str, Any]) -> str:
    """SHA-256 (hex) of the canonical JSON of action_payload.

    Canonical JSON means: keys sorted, separators (',', ':'), UTF-8.
    The same payload always gives the same hash, whatever the key order.
    NaN and Infinity are rejected because they are not valid JSON.
    """
    canonical = json.dumps(
        action_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
