"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.action_payloads
"""

from typing import Union

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
)


class FinanceGetReportPayload(BaseModel):
    """action_payload schema for FINANCE_GET_REPORT."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    report_id: str = Field(..., min_length=1, max_length=64)
    period: str = Field(..., min_length=1, max_length=16)


class FinanceGenerateSummaryPayload(BaseModel):
    """action_payload schema for FINANCE_GENERATE_SUMMARY."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    report_id: str = Field(..., min_length=1, max_length=64)
    period: str = Field(..., min_length=1, max_length=16)


class FinanceProposePaymentPayload(BaseModel):
    """action_payload schema for FINANCE_PROPOSE_PAYMENT."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    payee_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., ge=0.01, le=100000000.0)
    currency: str = Field(..., min_length=3, max_length=3)
    reference: str = Field(..., min_length=1, max_length=100)


class FinanceAccessSensitiveRecordsPayload(BaseModel):
    """action_payload schema for FINANCE_ACCESS_SENSITIVE_RECORDS."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    record_set: str = Field(..., min_length=1, max_length=64)
    record_count: int = Field(..., ge=1, le=1000000)
    justification: str = Field(..., min_length=1, max_length=500)


class SupportGetTicketPayload(BaseModel):
    """action_payload schema for SUPPORT_GET_TICKET."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    ticket_id: str = Field(..., min_length=1, max_length=64)


class SupportGenerateResponsePayload(BaseModel):
    """action_payload schema for SUPPORT_GENERATE_RESPONSE."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    ticket_id: str = Field(..., min_length=1, max_length=64)
    tone: str = Field(..., min_length=1, max_length=16)


class SupportProposeRefundPayload(BaseModel):
    """action_payload schema for SUPPORT_PROPOSE_REFUND."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    ticket_id: str = Field(..., min_length=1, max_length=64)
    customer_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., ge=0.01, le=100000000.0)
    currency: str = Field(..., min_length=3, max_length=3)
    reason: str = Field(..., min_length=1, max_length=500)


class SupportAccessCustomerInfoPayload(BaseModel):
    """action_payload schema for SUPPORT_ACCESS_CUSTOMER_INFO."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    customer_id: str = Field(..., min_length=1, max_length=64)
    fields: list[str]
    justification: str = Field(..., min_length=1, max_length=500)


class ItGetServerStatusPayload(BaseModel):
    """action_payload schema for IT_GET_SERVER_STATUS."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    server_id: str = Field(..., min_length=1, max_length=64)


class ItAnalyzeLogsPayload(BaseModel):
    """action_payload schema for IT_ANALYZE_LOGS."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    server_id: str = Field(..., min_length=1, max_length=64)
    window_minutes: int = Field(..., ge=1, le=1440)


class ItRestartServerPayload(BaseModel):
    """action_payload schema for IT_RESTART_SERVER."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    server_id: str = Field(..., min_length=1, max_length=64)
    environment: str = Field(..., min_length=1, max_length=16)
    reason: str = Field(..., min_length=1, max_length=500)


class ItChangePrivilegedConfigPayload(BaseModel):
    """action_payload schema for IT_CHANGE_PRIVILEGED_CONFIG."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    server_id: str = Field(..., min_length=1, max_length=64)
    environment: str = Field(..., min_length=1, max_length=16)
    config_key: str = Field(..., min_length=1, max_length=100)
    new_value: str = Field(..., min_length=0, max_length=500)
    reason: str = Field(..., min_length=1, max_length=500)


ActionPayload = Union[FinanceGetReportPayload, FinanceGenerateSummaryPayload, FinanceProposePaymentPayload, FinanceAccessSensitiveRecordsPayload, SupportGetTicketPayload, SupportGenerateResponsePayload, SupportProposeRefundPayload, SupportAccessCustomerInfoPayload, ItGetServerStatusPayload, ItAnalyzeLogsPayload, ItRestartServerPayload, ItChangePrivilegedConfigPayload]

# ActionType -> payload model (spec: ACTION_PAYLOAD_MODELS)
ACTION_PAYLOAD_MODELS: dict[ActionType, type[BaseModel]] = {
    ActionType.FINANCE_GET_REPORT: FinanceGetReportPayload,
    ActionType.FINANCE_GENERATE_SUMMARY: FinanceGenerateSummaryPayload,
    ActionType.FINANCE_PROPOSE_PAYMENT: FinanceProposePaymentPayload,
    ActionType.FINANCE_ACCESS_SENSITIVE_RECORDS: FinanceAccessSensitiveRecordsPayload,
    ActionType.SUPPORT_GET_TICKET: SupportGetTicketPayload,
    ActionType.SUPPORT_GENERATE_RESPONSE: SupportGenerateResponsePayload,
    ActionType.SUPPORT_PROPOSE_REFUND: SupportProposeRefundPayload,
    ActionType.SUPPORT_ACCESS_CUSTOMER_INFO: SupportAccessCustomerInfoPayload,
    ActionType.IT_GET_SERVER_STATUS: ItGetServerStatusPayload,
    ActionType.IT_ANALYZE_LOGS: ItAnalyzeLogsPayload,
    ActionType.IT_RESTART_SERVER: ItRestartServerPayload,
    ActionType.IT_CHANGE_PRIVILEGED_CONFIG: ItChangePrivilegedConfigPayload,
}
