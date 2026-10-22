import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core import execution_grant as eg
from app.core.config import get_settings
from app.core.enums import ActionType, ErrorCode
from app.core.exceptions import AppError
from app.core.hashing import compute_payload_hash
from app.schemas import ExecutionGrant, ToolInvocationRequest

SECRET_A = "a" * 40
PAYLOAD = {"payee_id": "p1", "amount": 100.5, "currency": "USD", "reference": "inv-1"}


@pytest.fixture(autouse=True)
def settings_and_clean_nonces(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", SECRET_A)
    monkeypatch.setenv("EXECUTION_GRANT_TTL_SECONDS", "60")
    get_settings.cache_clear()
    eg.reset_nonce_store()
    yield
    eg.reset_nonce_store()
    get_settings.cache_clear()


def make_call(payload=None, tool="finance_propose_payment_sim"):
    payload = payload if payload is not None else dict(PAYLOAD)
    ex, act = uuid.uuid4(), uuid.uuid4()
    invocation = ToolInvocationRequest(
        execution_id=ex, action_id=act, tool_name=tool,
        action_type=ActionType.FINANCE_PROPOSE_PAYMENT, action_payload=payload,
    )
    grant = eg.mint_execution_grant(ex, act, tool, compute_payload_hash(payload))
    return grant, invocation


def code_of(exc_info) -> ErrorCode:
    return exc_info.value.error_code


# --- minting ---------------------------------------------------------------------------

def test_mint_returns_a_signed_grant():
    grant, _ = make_call()
    assert isinstance(grant, ExecutionGrant)
    assert len(grant.signature) == 64 and int(grant.signature, 16) >= 0
    assert len(grant.nonce) == 32


def test_expiry_uses_ttl_from_settings(monkeypatch):
    monkeypatch.setenv("EXECUTION_GRANT_TTL_SECONDS", "10")
    get_settings.cache_clear()
    before = datetime.now(timezone.utc)
    grant, _ = make_call()
    assert timedelta(seconds=9) < grant.expires_at - before <= timedelta(seconds=10, milliseconds=500)


def test_every_grant_has_a_new_nonce():
    nonces = {make_call()[0].nonce for _ in range(50)}
    assert len(nonces) == 50


def test_signature_depends_on_the_secret(monkeypatch):
    ex, act = uuid.uuid4(), uuid.uuid4()
    h = compute_payload_hash(PAYLOAD)
    first = eg.mint_execution_grant(ex, act, "t", h)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "b" * 40)
    get_settings.cache_clear()
    inv = ToolInvocationRequest(execution_id=ex, action_id=act, tool_name="t",
                                action_type=ActionType.FINANCE_PROPOSE_PAYMENT, action_payload=PAYLOAD)
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(first, inv)  # signed with the old secret
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID


# --- the happy path ----------------------------------------------------------------------

def test_valid_grant_is_accepted_once():
    grant, inv = make_call()
    assert eg.verify_execution_grant(grant, inv) is None


def test_grant_survives_json_round_trip():
    grant, inv = make_call()
    restored = ExecutionGrant.model_validate_json(grant.model_dump_json())
    eg.verify_execution_grant(restored, inv)


# --- no grant ----------------------------------------------------------------------------

def test_no_grant_means_direct_execution_forbidden():
    _, inv = make_call()
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(None, inv)
    assert code_of(e) == ErrorCode.DIRECT_EXECUTION_FORBIDDEN


def test_a_non_grant_object_is_forbidden():
    _, inv = make_call()
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant({"signature": "x"}, inv)
    assert code_of(e) == ErrorCode.DIRECT_EXECUTION_FORBIDDEN


# --- forged or tampered grants ------------------------------------------------------------

def test_forged_signature_is_rejected():
    grant, inv = make_call()
    forged = grant.model_copy(update={"signature": "0" * 64})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(forged, inv)
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID
    assert e.value.details == {"reason": "bad_signature"}


def test_non_ascii_signature_does_not_crash():
    grant, inv = make_call()
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant.model_copy(update={"signature": "é" * 64}), inv)
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID


@pytest.mark.parametrize("field,new_value", [
    ("execution_id", uuid.uuid4()),
    ("action_id", uuid.uuid4()),
    ("tool_name", "another_tool"),
    ("payload_hash", "f" * 64),
    ("nonce", "0" * 32),
    ("expires_at", datetime.now(timezone.utc) + timedelta(days=1)),
])
def test_changing_any_signed_field_breaks_the_signature(field, new_value):
    grant, inv = make_call()
    tampered = grant.model_copy(update={field: new_value})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(tampered, inv)
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID
    assert e.value.details == {"reason": "bad_signature"}


# --- expiry -------------------------------------------------------------------------------

def test_expired_grant_is_rejected(monkeypatch):
    grant, inv = make_call()
    later = datetime.now(timezone.utc) + timedelta(seconds=61)
    monkeypatch.setattr(eg, "_now", lambda: later)
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant, inv)
    assert e.value.details == {"reason": "expired"}


def test_grant_is_valid_just_before_expiry(monkeypatch):
    grant, inv = make_call()
    monkeypatch.setattr(eg, "_now", lambda: grant.expires_at - timedelta(seconds=1))
    eg.verify_execution_grant(grant, inv)


def test_grant_without_timezone_is_rejected():
    grant, inv = make_call()
    naive = grant.model_copy(update={"expires_at": grant.expires_at.replace(tzinfo=None)})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(naive, inv)
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID


# --- binding to the call ----------------------------------------------------------------------

def test_wrong_payload_is_rejected():
    grant, inv = make_call()
    changed = inv.model_copy(update={"action_payload": {**PAYLOAD, "amount": 999999}})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant, changed)
    assert e.value.details == {"reason": "payload_changed"}


@pytest.mark.parametrize("field,new_value", [
    ("execution_id", uuid.uuid4()), ("action_id", uuid.uuid4()), ("tool_name", "other_tool"),
])
def test_grant_is_bound_to_execution_action_and_tool(field, new_value):
    grant, inv = make_call()
    other = inv.model_copy(update={field: new_value})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant, other)
    assert e.value.details == {"reason": "binding_mismatch"}


def test_nan_payload_is_rejected_not_crashed():
    grant, inv = make_call()
    bad = inv.model_copy(update={"action_payload": {"amount": float("nan")}})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant, bad)
    assert code_of(e) == ErrorCode.EXECUTION_GRANT_INVALID


def test_payload_key_order_does_not_matter():
    grant, inv = make_call()
    reordered = inv.model_copy(update={"action_payload": dict(reversed(list(PAYLOAD.items())))})
    eg.verify_execution_grant(grant, reordered)


# --- single use ---------------------------------------------------------------------------------

def test_replayed_nonce_is_rejected():
    grant, inv = make_call()
    eg.verify_execution_grant(grant, inv)
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(grant, inv)
    assert e.value.details == {"reason": "nonce_already_used"}


def test_two_different_grants_both_work():
    for _ in range(2):
        grant, inv = make_call()
        eg.verify_execution_grant(grant, inv)


def test_failed_check_does_not_burn_the_nonce():
    grant, inv = make_call()
    wrong = inv.model_copy(update={"tool_name": "other"})
    with pytest.raises(AppError):
        eg.verify_execution_grant(grant, wrong)
    eg.verify_execution_grant(grant, inv)  # still usable for the right call


def test_forged_grant_cannot_poison_the_nonce_store():
    grant, inv = make_call()
    forged = grant.model_copy(update={"signature": "1" * 64})
    with pytest.raises(AppError):
        eg.verify_execution_grant(forged, inv)
    eg.verify_execution_grant(grant, inv)


def test_old_nonces_are_forgotten(monkeypatch):
    grant, inv = make_call()
    eg.verify_execution_grant(grant, inv)
    assert grant.nonce in eg._used_nonces
    later = datetime.now(timezone.utc) + timedelta(seconds=120)
    monkeypatch.setattr(eg, "_now", lambda: later)
    # a grant minted at the later time; verifying it purges the expired entry
    fresh, fresh_inv = make_call()
    eg.verify_execution_grant(fresh, fresh_inv)
    assert grant.nonce not in eg._used_nonces
    assert fresh.nonce in eg._used_nonces


def test_only_one_of_many_concurrent_uses_succeeds():
    grant, inv = make_call()
    results = []

    def attempt():
        try:
            eg.verify_execution_grant(grant, inv)
            results.append("ok")
        except AppError:
            results.append("rejected")

    threads = [threading.Thread(target=attempt) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1 and results.count("rejected") == 29


# --- safety of messages -------------------------------------------------------------------------

def test_error_never_contains_the_secret():
    grant, inv = make_call()
    forged = grant.model_copy(update={"signature": "0" * 64})
    with pytest.raises(AppError) as e:
        eg.verify_execution_grant(forged, inv)
    text = f"{e.value.error_message} {e.value.details}"
    assert SECRET_A not in text and grant.signature not in text


def test_http_status_of_grant_errors_is_500_as_in_spec():
    assert AppError(ErrorCode.EXECUTION_GRANT_INVALID, "x").http_status == 500
    assert AppError(ErrorCode.DIRECT_EXECUTION_FORBIDDEN, "x").http_status == 500


# --- how a tool is expected to use it (the BaseTool.invoke pattern from the spec) ---------------------

class FakeTool:
    """Same shape as BaseTool.invoke in the spec: verify first, then run."""

    def __init__(self):
        self.runs = 0

    async def invoke(self, invocation, grant):
        eg.verify_execution_grant(grant, invocation)
        return await self._run(invocation)

    async def _run(self, invocation):
        self.runs += 1
        return "done"


async def test_tool_body_runs_only_with_a_valid_grant():
    tool = FakeTool()
    grant, inv = make_call()
    with pytest.raises(AppError):
        await tool.invoke(inv, None)
    with pytest.raises(AppError):
        await tool.invoke(inv, grant.model_copy(update={"signature": "0" * 64}))
    assert tool.runs == 0
    assert await tool.invoke(inv, grant) == "done"
    with pytest.raises(AppError):
        await tool.invoke(inv, grant)  # replay
    assert tool.runs == 1
