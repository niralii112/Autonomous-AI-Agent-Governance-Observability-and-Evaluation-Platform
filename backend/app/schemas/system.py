"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.system
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    HealthStatus,
    RiskSource,
)


class ComponentHealth(BaseModel):
    """Health of one component."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    component_name: str
    status: HealthStatus
    latency_ms: float | None
    detail: str | None


class HealthResponse(BaseModel):
    """Public health. Governance components DOWN => system DOWN; telemetry or risk-model problems => DEGRADED."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    status: HealthStatus
    version: str
    checked_at: datetime
    components: list[ComponentHealth]


class SystemInfoResponse(BaseModel):
    """Build and configuration facts."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    app_version: str
    contract_version: str
    api_version: str
    environment: str
    active_model_version: str | None
    active_risk_source: RiskSource
    approval_ttl_seconds: int
    risk_threshold_medium: float
    risk_threshold_high: float
    risk_threshold_critical: float
