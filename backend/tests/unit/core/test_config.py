import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.enums import GovernanceDecision

JWT = "j" * 40
GRANT = "g" * 40


def make(**overrides):
    values = dict(
        postgres_password="pw",
        database_url="postgresql+psycopg://u:pw@localhost:5432/db",
        jwt_secret_key=JWT,
        execution_grant_secret=GRANT,
    )
    values.update(overrides)
    # _env_file=None so a developer's real .env cannot change the test result
    return Settings(_env_file=None, **values)


def test_defaults_match_spec():
    s = make()
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_access_token_expire_minutes == 60
    assert s.execution_grant_ttl_seconds == 60
    assert s.execution_timeout_seconds == 30
    assert s.execution_max_attempts == 3
    assert s.approval_ttl_seconds == 3600
    assert s.approval_sweep_interval_seconds == 30
    assert s.governance_no_match_decision == GovernanceDecision.HUMAN_REVIEW
    assert (s.risk_threshold_medium, s.risk_threshold_high, s.risk_threshold_critical) == (
        0.30,
        0.60,
        0.85,
    )
    assert s.risk_model_version == "risk-logreg-1.0.0"


def test_missing_required_secrets_fail():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_no_match_decision_allow_is_rejected():
    with pytest.raises(ValidationError):
        make(governance_no_match_decision="ALLOW")


def test_no_match_decision_block_is_accepted():
    assert make(governance_no_match_decision="BLOCK").governance_no_match_decision == (
        GovernanceDecision.BLOCK
    )


def test_empty_secret_is_rejected():
    with pytest.raises(ValidationError):
        make(jwt_secret_key="   ")


def test_short_secret_is_rejected():
    with pytest.raises(ValidationError):
        make(execution_grant_secret="short")


def test_secrets_must_differ():
    with pytest.raises(ValidationError):
        make(execution_grant_secret=JWT)


def test_placeholder_secret_allowed_locally_but_not_in_production():
    placeholder = "CHANGE_ME_GENERATE_RANDOM_64_HEX"
    assert make(jwt_secret_key=placeholder, app_env="local")
    with pytest.raises(ValidationError):
        make(jwt_secret_key=placeholder, app_env="production")


def test_thresholds_must_be_increasing():
    with pytest.raises(ValidationError):
        make(risk_threshold_medium=0.7)


def test_cors_origins_are_split():
    s = make(cors_allowed_origins="http://a.com, http://b.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com"]


def test_extra_env_values_are_ignored():
    assert make(some_unknown_value="x")


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:pw@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", JWT)
    monkeypatch.setenv("EXECUTION_GRANT_SECRET", GRANT)
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
