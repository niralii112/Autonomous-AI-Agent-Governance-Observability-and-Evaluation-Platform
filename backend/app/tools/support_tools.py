
"""Simulated customer-support tools for governance demonstrations."""

from __future__ import annotations

from typing import Any, Mapping

from app.tools.base import BaseTool, GrantVerifier


class CustomerInfoReaderTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="customer_info_reader",
            description="Returns synthetic customer-support information.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        customer_id = payload.get("customer_id")
        if not isinstance(customer_id, str) or not customer_id.strip():
            raise ValueError("customer_id is required")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED",
            "customer_id": payload["customer_id"],
            "data": {
                "message": "Synthetic customer information; no real data accessed."
            },
        }


class RefundProposalTool(BaseTool):
    def __init__(
        self,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        super().__init__(
            tool_name="refund_proposal",
            description="Creates a simulated refund proposal.",
            grant_verifier=grant_verifier,
        )

    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        amount = payload.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("amount must be numeric")

        if amount <= 0:
            raise ValueError("amount must be positive")

        ticket_id = payload.get("ticket_id")
        if not isinstance(ticket_id, str) or not ticket_id.strip():
            raise ValueError("ticket_id is required")

    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status": "SIMULATED_REFUND_PROPOSAL_CREATED",
            "ticket_id": payload["ticket_id"],
            "amount": float(payload["amount"]),
            "refund_issued": False,
        }
