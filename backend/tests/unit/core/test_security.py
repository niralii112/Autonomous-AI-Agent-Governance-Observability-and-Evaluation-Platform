import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core import security
from app.core.config import get_settings
from app.core.enums import ErrorCode, UserRole
from app.core.exceptions import AppError

JWT_SECRET = "j" * 40
UID = uuid.uuid4()


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:x@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", "g" * 40)
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)  # fast hashing in tests
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- passwords ------------------------------------------------------------------------------

def test_hash_and_verify():
    h = security.hash_password("CorrectHorse-Battery-9")
    assert security.verify_password("CorrectHorse-Battery-9", h)
    assert not security.verify_password("wrong-password-123", h)


def test_hash_is_bcrypt_and_salted():
    a, b = security.hash_password("same-password-12"), security.hash_password("same-password-12")
    assert a.startswith("$2b$") and a != b
    assert len(a) <= 255  # fits users.password_hash varchar(255)


def test_password_is_not_stored_in_the_hash():
    assert "same-password-12" not in security.hash_password("same-password-12")


def test_128_character_password_works():
    pw = "x" * 128
    assert security.verify_password(pw, security.hash_password(pw))


def test_passwords_differing_only_after_byte_72_are_different():
    base = "a" * 80
    h = security.hash_password(base + "1")
    assert security.verify_password(base + "1", h)
    assert not security.verify_password(base + "2", h)  # plain bcrypt would accept this


def test_unicode_and_nul_bytes_are_fine():
    for pw in ["pässwörd-日本語-123", "with\x00nul-byte-123"]:
        assert security.verify_password(pw, security.hash_password(pw))


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "$2b$04$short", None])
def test_verify_with_malformed_hash_is_false_not_an_error(bad_hash):
    assert security.verify_password("whatever-123456", bad_hash) is False


def test_burn_password_check_does_not_raise():
    security.burn_password_check("anything")


# --- tokens -----------------------------------------------------------------------------------

def make_token(**overrides):
    now = int(time.time())
    claims = {"sub": str(UID), "username": "nirali", "role": "ADMIN",
              "iss": "agent-governance-platform", "iat": now, "exp": now + 3600}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def code(exc_info):
    return exc_info.value.error_code


def test_token_round_trip_has_all_spec_claims():
    token = security.create_access_token(UID, "nirali", UserRole.ADMIN)
    claims = security.decode_access_token(token)
    assert claims["sub"] == str(UID)
    assert claims["username"] == "nirali"
    assert claims["role"] == "ADMIN"
    assert claims["iss"] == "agent-governance-platform"
    assert claims["exp"] - claims["iat"] == 3600


def test_lifetime_follows_the_setting(monkeypatch):
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    get_settings.cache_clear()
    claims = security.decode_access_token(security.create_access_token(UID, "u", UserRole.VIEWER))
    assert claims["exp"] - claims["iat"] == 300
    assert security.access_token_lifetime_seconds() == 300


def test_token_header_says_hs256():
    token = security.create_access_token(UID, "u", UserRole.VIEWER)
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_token_contains_no_password_or_secret():
    token = security.create_access_token(UID, "u", UserRole.VIEWER)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert set(payload) == {"sub", "username", "role", "iss", "iat", "exp"}


def test_expired_token():
    with pytest.raises(AppError) as e:
        security.decode_access_token(make_token(exp=int(time.time()) - 10))
    assert code(e) == ErrorCode.AUTH_TOKEN_EXPIRED


def test_wrong_secret():
    forged = jwt.encode({"sub": str(UID)}, "x" * 40, algorithm="HS256")
    with pytest.raises(AppError) as e:
        security.decode_access_token(forged)
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


def test_algorithm_none_is_rejected():
    now = int(time.time())
    unsigned = jwt.encode({"sub": str(UID), "username": "u", "role": "ADMIN",
                           "iss": "agent-governance-platform", "iat": now, "exp": now + 99},
                          key=None, algorithm="none")
    with pytest.raises(AppError) as e:
        security.decode_access_token(unsigned)
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


@pytest.mark.filterwarnings("ignore:The HMAC key")
def test_other_hmac_algorithm_is_rejected():
    now = int(time.time())
    token = jwt.encode({"sub": str(UID), "username": "u", "role": "ADMIN",
                        "iss": "agent-governance-platform", "iat": now, "exp": now + 99},
                       JWT_SECRET, algorithm="HS512")
    with pytest.raises(AppError) as e:
        security.decode_access_token(token)
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


def test_wrong_issuer():
    with pytest.raises(AppError) as e:
        security.decode_access_token(make_token(iss="someone-else"))
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


@pytest.mark.parametrize("missing", ["sub", "username", "role", "iss", "iat", "exp"])
def test_every_required_claim_must_be_present(missing):
    now = int(time.time())
    claims = {"sub": str(UID), "username": "u", "role": "ADMIN",
              "iss": "agent-governance-platform", "iat": now, "exp": now + 99}
    del claims[missing]
    with pytest.raises(AppError) as e:
        security.decode_access_token(jwt.encode(claims, JWT_SECRET, algorithm="HS256"))
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


@pytest.mark.parametrize("override", [{"sub": "not-a-uuid"}, {"role": "SUPERUSER"}, {"role": "admin"}])
def test_bad_claim_values_are_rejected(override):
    with pytest.raises(AppError) as e:
        security.decode_access_token(make_token(**override))
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "Bearer xyz"])
def test_garbage_is_invalid(garbage):
    with pytest.raises(AppError) as e:
        security.decode_access_token(garbage)
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID


def test_tampered_payload_is_rejected():
    token = security.create_access_token(UID, "u", UserRole.VIEWER)
    header, payload, sig = token.split(".")
    import base64, json
    data = json.loads(base64.urlsafe_b64decode(payload + "=="))
    data["role"] = "ADMIN"
    forged_payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    with pytest.raises(AppError) as e:
        security.decode_access_token(f"{header}.{forged_payload}.{sig}")
    assert code(e) == ErrorCode.AUTH_TOKEN_INVALID
