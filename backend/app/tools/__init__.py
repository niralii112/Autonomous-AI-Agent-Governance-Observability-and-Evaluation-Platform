
"""Tool registry for simulated governance-controlled tools."""

from app.tools.base import BaseTool, ToolInvocationError
from app.tools.finance_tools import (
    FinanceRecordsReaderTool,
    FinanceReportReaderTool,
    FinanceSummaryGeneratorTool,
    PaymentProposalTool,
)
from app.tools.support_tools import (
    CustomerInfoReaderTool,
    RefundProposalTool,
    SupportResponseGeneratorTool,
    TicketReaderTool,
)


def build_tool_registry(
    grant_verifier=None,
) -> dict[str, BaseTool]:
    """Build the tool registry with the supplied execution-grant verifier."""

    tools: list[BaseTool] = [
        PaymentProposalTool(grant_verifier),
        FinanceRecordsReaderTool(grant_verifier),
        FinanceReportReaderTool(grant_verifier),
        FinanceSummaryGeneratorTool(grant_verifier),
        CustomerInfoReaderTool(grant_verifier),
        RefundProposalTool(grant_verifier),
        TicketReaderTool(grant_verifier),
        SupportResponseGeneratorTool(grant_verifier),
    ]

    return {tool.tool_name: tool for tool in tools}


__all__ = [
    "BaseTool",
    "ToolInvocationError",
    "PaymentProposalTool",
    "FinanceRecordsReaderTool",
    "FinanceReportReaderTool",
    "FinanceSummaryGeneratorTool",
    "CustomerInfoReaderTool",
    "RefundProposalTool",
    "TicketReaderTool",
    "SupportResponseGeneratorTool",
    "build_tool_registry",
]
