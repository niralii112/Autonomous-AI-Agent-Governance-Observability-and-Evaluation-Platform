
import pytest

from app.tools import build_tool_registry
from app.schemas.tool_runtime import ExecutionGrant, ToolInvocationRequest


def test_registry_contains_expected_tools():
    registry = build_tool_registry()

    assert set(registry) == {
        "payment_proposal",
        "finance_records_reader",
        "customer_info_reader",
        "refund_proposal",
    }


def test_tool_invocation_fails_closed_without_grant_verifier():
    registry = build_tool_registry()
    tool = registry["customer_info_reader"]

    request = ToolInvocationRequest(
        execution_id="00000000-0000-0000-0000-000000000001",
        action_id="00000000-0000-0000-0000-000000000002",
        tool_name="customer_info_reader",
        action_type="SUPPORT_ACCESS_CUSTOMER_INFO",
        action_payload={"customer_id": "customer-123"},
    )

    grant = ExecutionGrant(
        execution_id=request.execution_id,
        action_id=request.action_id,
        tool_name=request.tool_name,
        payload_hash="test-hash",
        expires_at="2099-01-01T00:00:00Z",
        nonce="test-nonce",
        signature="test-signature",
    )

    with pytest.raises(Exception):
        tool.invoke(request, grant)
