
"""Simulated finance tools for governance-controlled demonstrations."""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.tools.base import BaseTool, GrantVerifier


def _require_non_empty_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


class PaymentProposalTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="payment_processor_sim",
            description="Creates a simulated payment proposal; no external payment is sent.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "payee_id")
        _require_non_empty_string(payload, "reference")

        amount = payload.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("amount must be numeric")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("amount must be positive and finite")

        currency = payload.get("currency")
        if (
            not isinstance(currency, str)
            or len(currency) != 3
            or not currency.isalpha()
        ):
            raise ValueError("currency must be a three-letter code")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED_PAYMENT_PROPOSAL_CREATED",
            "payee_id": str(payload["payee_id"]),
            "amount": float(payload["amount"]),
            "currency": str(payload["currency"]).upper(),
            "reference": str(payload["reference"]),
            "external_payment_sent": False,
        }


class FinanceRecordsReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="finance_records_vault",
            description="Returns synthetic finance-record information only.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "record_set")
        _require_non_empty_string(payload, "justification")

        record_count = payload.get("record_count")
        if (
            isinstance(record_count, bool)
            or not isinstance(record_count, int)
            or record_count <= 0
        ):
            raise ValueError("record_count must be a positive integer")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "record_set": str(payload["record_set"]),
            "record_count": payload["record_count"],
            "data": {
                "message": "Synthetic demo data only; no real finance records accessed."
            },
        }


class FinanceReportReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="finance_report_reader",
            description="Reads a synthetic finance report.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "report_id")
        _require_non_empty_string(payload, "period")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "report_id": str(payload["report_id"]),
            "period": str(payload["period"]),
            "report": {
                "message": "Synthetic quarterly finance report; no real financial data accessed."
            },
        }


class FinanceSummaryGeneratorTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="finance_summary_generator",
            description="Generates a summary from synthetic finance-report data.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "report_id")
        _require_non_empty_string(payload, "period")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "report_id": str(payload["report_id"]),
            "period": str(payload["period"]),
            "summary": "Synthetic finance summary generated for demonstration.",
        }
