
"""Simulated customer-support tools for governance-controlled demonstrations."""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.tools.base import BaseTool, GrantVerifier


def _require_non_empty_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


class CustomerInfoReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="customer_info_accessor",
            description="Returns synthetic customer information only.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "customer_id")
        _require_non_empty_string(payload, "justification")

        fields = payload.get("fields")
        if (
            not isinstance(fields, list)
            or not fields
            or any(not isinstance(field, str) or not field.strip() for field in fields)
        ):
            raise ValueError("fields must be a non-empty list of strings")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "customer_id": str(payload["customer_id"]),
            "requested_fields": payload["fields"],
            "data": {
                "message": (
                    "Synthetic customer information only; "
                    "no real customer records accessed."
                )
            },
        }


class RefundProposalTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="refund_processor_sim",
            description="Creates a simulated refund proposal; no refund is issued.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "ticket_id")
        _require_non_empty_string(payload, "customer_id")
        _require_non_empty_string(payload, "reason")

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
            "status": "SIMULATED_REFUND_PROPOSAL_CREATED",
            "ticket_id": str(payload["ticket_id"]),
            "customer_id": str(payload["customer_id"]),
            "amount": float(payload["amount"]),
            "currency": str(payload["currency"]).upper(),
            "reason": str(payload["reason"]),
            "refund_issued": False,
        }


class TicketReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="ticket_reader",
            description="Reads synthetic customer-support ticket information.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "ticket_id")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "ticket_id": str(payload["ticket_id"]),
            "ticket": {
                "subject": "Synthetic support ticket",
                "message": "This is demonstration data; no real ticket was accessed.",
            },
        }


class SupportResponseGeneratorTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="support_response_generator",
            description="Generates a simulated support response draft; no message is sent.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        _require_non_empty_string(payload, "ticket_id")

        tone = payload.get("tone")
        allowed_tones = {"FRIENDLY", "PROFESSIONAL", "EMPATHETIC"}
        if not isinstance(tone, str) or tone.upper() not in allowed_tones:
            raise ValueError("tone must be FRIENDLY, PROFESSIONAL, or EMPATHETIC")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        tone = str(payload["tone"]).upper()

        return {
            "status": "SIMULATED_RESPONSE_GENERATED",
            "ticket_id": str(payload["ticket_id"]),
            "tone": tone,
            "draft": (
                "Thank you for contacting us. We understand your concern "
                "and are happy to help. Our team will review your request."
            ),
            "message_sent": False,
        }
