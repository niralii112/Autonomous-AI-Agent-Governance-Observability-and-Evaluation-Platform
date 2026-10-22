"""Execution grants (spec section 12, mint_execution_grant / verify_execution_grant).

A grant is a short-lived, single-use, signed permission to run ONE tool call for ONE
execution attempt. Only execution_service mints grants (after the execution row has moved
PENDING -> RUNNING). Every tool calls verify_execution_grant before it does anything.

How the signature is built (the spec fixes HMAC-SHA256 and the six fields; this module
fixes the exact byte format so mint and verify always agree):
    message   = JSON array, no spaces:
                [execution_id, action_id, tool_name, payload_hash, expires_at_utc_iso, nonce]
    signature = HMAC-SHA256(EXECUTION_GRANT_SECRET, message) as lowercase hex
"""

import hashlib
import hmac
import json
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.enums import ErrorCode
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas.tool_runtime import ExecutionGrant, ToolInvocationRequest

# Nonces already used, kept in process memory (spec: "single-use in process memory").
# The value is the grant's expiry, so old entries can be dropped to keep memory bounded.
_used_nonces: dict[str, datetime] = {}
_nonce_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sign(
    execution_id: uuid.UUID,
    action_id: uuid.UUID,
    tool_name: str,
    payload_hash: str,
    expires_at: datetime,
    nonce: str,
) -> str:
    message = json.dumps(
        [
            str(execution_id),
            str(action_id),
            tool_name,
            payload_hash,
            expires_at.astimezone(timezone.utc).isoformat(),
            nonce,
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    key = get_settings().execution_grant_secret.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def mint_execution_grant(
    execution_id: uuid.UUID,
    action_id: uuid.UUID,
    tool_name: str,
    payload_hash: str,
) -> ExecutionGrant:
    """Create a signed grant that expires after EXECUTION_GRANT_TTL_SECONDS."""
    expires_at = _now() + timedelta(seconds=get_settings().execution_grant_ttl_seconds)
    nonce = secrets.token_hex(16)
    return ExecutionGrant(
        execution_id=execution_id,
        action_id=action_id,
        tool_name=tool_name,
        payload_hash=payload_hash,
        expires_at=expires_at,
        nonce=nonce,
        signature=_sign(execution_id, action_id, tool_name, payload_hash, expires_at, nonce),
    )


def _invalid(reason: str) -> AppError:
    # The reason is for logs and audit. It never contains the secret or the expected values.
    return AppError(
        ErrorCode.EXECUTION_GRANT_INVALID,
        "Execution grant is not valid for this tool call.",
        {"reason": reason},
    )


def verify_execution_grant(grant: ExecutionGrant | None, invocation: ToolInvocationRequest) -> None:
    """Raise AppError unless the grant is genuine, fresh, bound to this call and unused.

    - No grant at all         -> DIRECT_EXECUTION_FORBIDDEN
    - Anything else wrong     -> EXECUTION_GRANT_INVALID
    On success the nonce is consumed, so the same grant can never be used twice.
    """
    if grant is None or not isinstance(grant, ExecutionGrant):
        raise AppError(
            ErrorCode.DIRECT_EXECUTION_FORBIDDEN,
            "Tools can only run through governed execution with a valid grant.",
        )
    if grant.expires_at.tzinfo is None:
        raise _invalid("expires_at_has_no_timezone")

    # 1. Signature first, so a forged grant can never touch the nonce store.
    expected = _sign(
        grant.execution_id,
        grant.action_id,
        grant.tool_name,
        grant.payload_hash,
        grant.expires_at,
        grant.nonce,
    )
    if not hmac.compare_digest(expected.encode("utf-8"), grant.signature.encode("utf-8")):
        raise _invalid("bad_signature")

    # 2. Expiry.
    now = _now()
    if grant.expires_at <= now:
        raise _invalid("expired")

    # 3. The grant must be for exactly this call, and the payload must be unchanged.
    if (
        grant.execution_id != invocation.execution_id
        or grant.action_id != invocation.action_id
        or grant.tool_name != invocation.tool_name
    ):
        raise _invalid("binding_mismatch")
    try:
        recomputed = compute_payload_hash(invocation.action_payload)
    except (TypeError, ValueError):
        raise _invalid("payload_not_hashable") from None
    if not hmac.compare_digest(recomputed.encode("utf-8"), grant.payload_hash.encode("utf-8")):
        raise _invalid("payload_changed")

    # 4. Single use. Check-and-add happens under one lock, so two threads cannot both win.
    with _nonce_lock:
        for used, expiry in list(_used_nonces.items()):
            if expiry <= now:
                del _used_nonces[used]
        if grant.nonce in _used_nonces:
            raise _invalid("nonce_already_used")
        _used_nonces[grant.nonce] = grant.expires_at


def reset_nonce_store() -> None:
    """Forget all used nonces. For tests only."""
    with _nonce_lock:
        _used_nonces.clear()
