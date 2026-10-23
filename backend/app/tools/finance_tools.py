
"""Simulated finance tools for governance demonstrations."""

from __future__ import annotations

from typing import Any, Mapping

from app.tools.base import BaseTool, GrantVerifier


class PaymentProposalTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="payment_proposal",
            description="Creates a simulated payment proposal.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        amount = payload.get("amount")
        currency = payload.get("currency")

        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("amount must be numeric")

        if amount <= 0:
            raise ValueError("amount must be positive")

        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError("currency must be a three-character code")

        if not currency.isalpha():
            raise ValueError("currency must contain letters only")

        if len(str(payload.get("recipient_id", "")).strip()) == 0:
            raise ValueError("recipient_id is required")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED_PROPOSAL_CREATED",
            "recipient_id": str(payload["recipient_id"]),
            "amount": float(payload["amount"]),
            "currency": str(payload["currency"]).upper(),
            "external_payment_sent": False,
        }


class FinanceRecordsReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="finance_records_reader",
            description="Returns a synthetic finance-record summary.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        record_type = payload.get("record_type", "summary")
        if record_type not in {"summary", "budget", "invoice"}:
            raise ValueError("Unsupported synthetic record_type")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        record_type = payload.get("record_type", "summary")

        return {
            "status": "SIMULATED",
            "record_type": record_type,
            "data": {
                "message": "Synthetic demo data only; no real records accessed."
            },
        }
