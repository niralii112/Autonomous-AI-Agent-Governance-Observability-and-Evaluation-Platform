
"""Tool registry for simulated governance-controlled tools."""

from app.tools.base import BaseTool, ToolInvocationError
from app.tools.finance_tools import (
    FinanceRecordsReaderTool,
    PaymentProposalTool,
)
from app.tools.support_tools import (
    CustomerInfoReaderTool,
    RefundProposalTool,
)


def build_tool_registry(grant_verifier=None) -> dict[str, BaseTool]:
    """Build a registry. No verifier means invocation remains disabled."""

    tools: list[BaseTool] = [
        PaymentProposalTool(grant_verifier),
        FinanceRecordsReaderTool(grant_verifier),
        CustomerInfoReaderTool(grant_verifier),
        RefundProposalTool(grant_verifier),
    ]

    return {tool.tool_name: tool for tool in tools}


__all__ = [
    "BaseTool",
    "ToolInvocationError",
    "PaymentProposalTool",
    "FinanceRecordsReaderTool",
    "CustomerInfoReaderTool",
    "RefundProposalTool",
    "build_tool_registry",
]
