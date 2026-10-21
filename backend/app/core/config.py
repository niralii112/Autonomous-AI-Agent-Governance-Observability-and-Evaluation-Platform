"""Settings (spec section 9.8). Field names are the lowercase env var names."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import GovernanceDecision

_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_env: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: str = "http://localhost:5173"

    # Database
    postgres_user: str = "governance_user"
    postgres_password: str
    postgres_db: str = "governance_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "agent-governance-platform"
    jwt_access_token_expire_minutes: int = 60

    # Execution and approvals
    execution_grant_secret: str
    execution_grant_ttl_seconds: int = 60
    execution_timeout_seconds: int = 30
    execution_max_attempts: int = 3
    approval_ttl_seconds: int = 3600
    approval_sweep_interval_seconds: int = 30

    # Governance and risk
    governance_no_match_decision: GovernanceDecision = GovernanceDecision.HUMAN_REVIEW
    risk_threshold_medium: float = Field(default=0.30, ge=0.0, le=1.0)
    risk_threshold_high: float = Field(default=0.60, ge=0.0, le=1.0)
    risk_threshold_critical: float = Field(default=0.85, ge=0.0, le=1.0)
    risk_model_artifact_dir: str = "backend/artifacts"
    risk_model_version: str = "risk-logreg-1.0.0"

    # Telemetry
    otel_traces_enabled: bool = True
    otel_service_name: str = "governance-backend"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_exporter_otlp_protocol: str = "grpc"
    jaeger_query_url: str = "http://localhost:16686"
    telemetry_query_timeout_seconds: int = 5

    # Seed script only
    seed_admin_password: str | None = None
    seed_reviewer_password: str | None = None
    seed_operator_password: str | None = None
    seed_viewer_password: str | None = None

    # Docker and frontend values (kept so .env.example matches the spec)
    postgres_image: str = "postgres:16-alpine"
    otel_collector_image: str = "otel/opentelemetry-collector-contrib:latest"
    jaeger_image: str = "jaegertracing/jaeger:latest"
    vite_api_base_url: str = "http://localhost:8000/api/v1"
    vite_use_mocks: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_startup_rules(self) -> "Settings":
        # Fail closed: an unsafe configuration must stop the app from starting.
        if self.governance_no_match_decision == GovernanceDecision.ALLOW:
            raise ValueError("GOVERNANCE_NO_MATCH_DECISION must be HUMAN_REVIEW or BLOCK")

        secrets = {
            "JWT_SECRET_KEY": self.jwt_secret_key,
            "EXECUTION_GRANT_SECRET": self.execution_grant_secret,
        }
        for name, value in secrets.items():
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
            if len(value) < _MIN_SECRET_LENGTH:
                raise ValueError(f"{name} must be at least {_MIN_SECRET_LENGTH} characters")
            if "CHANGE_ME" in value and self.app_env not in ("local", "test"):
                raise ValueError(f"{name} still has the CHANGE_ME placeholder")
        if self.jwt_secret_key == self.execution_grant_secret:
            raise ValueError("EXECUTION_GRANT_SECRET must differ from JWT_SECRET_KEY")

        if not (
            self.risk_threshold_medium < self.risk_threshold_high < self.risk_threshold_critical
        ):
            raise ValueError("risk thresholds must satisfy MEDIUM < HIGH < CRITICAL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
