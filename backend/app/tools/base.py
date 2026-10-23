
"""Base class for governance-controlled tools.

Tools never mint their own execution grants. A tool can run only when
an external execution service provides a grant verifier that approves
the exact invocation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping

from app.core.enums import ErrorCode
from app.schemas.tool_runtime import ExecutionGrant, ToolInvocationRequest


GrantVerifier = Callable[
    [ExecutionGrant, ToolInvocationRequest],
    bool,
]


class ToolInvocationError(RuntimeError):
    """Raised when a tool invocation is invalid or not authorized."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code


class BaseTool(ABC):
    """Fail-closed base class for tools invoked by the execution service."""

    def __init__(
        self,
        *,
        tool_name: str,
        description: str,
        grant_verifier: GrantVerifier | None = None,
    ) -> None:
        if not tool_name.strip():
            raise ValueError("tool_name must not be empty")

        self.tool_name = tool_name
        self.description = description
        self._grant_verifier = grant_verifier

    @abstractmethod
    def validate_payload(self, payload: Mapping[str, Any]) -> None:
        """Raise ValueError when the tool payload is invalid."""

    @abstractmethod
    def execute(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Execute the tool's local, simulated operation."""

    def invoke(
        self,
        request: ToolInvocationRequest,
        grant: ExecutionGrant,
    ) -> dict[str, Any]:
        """Validate authorization and payload before invoking a tool."""

        if request.tool_name != self.tool_name:
            raise ToolInvocationError(
                ErrorCode.TOOL_NOT_AVAILABLE,
                "The requested tool does not match this tool instance.",
            )

        if (
            grant.execution_id != request.execution_id
            or grant.action_id != request.action_id
            or grant.tool_name != request.tool_name
        ):
            raise ToolInvocationError(
                ErrorCode.EXECUTION_GRANT_INVALID,
                "The execution grant does not match the invocation.",
            )

        if self._grant_verifier is None:
            raise ToolInvocationError(
                ErrorCode.EXECUTION_GRANT_INVALID,
                "No execution-grant verifier is configured.",
            )

        try:
            authorized = self._grant_verifier(grant, request)
        except Exception as exc:
            raise ToolInvocationError(
                ErrorCode.EXECUTION_GRANT_INVALID,
                "Execution-grant verification failed.",
            ) from exc

        if authorized is not True:
            raise ToolInvocationError(
                ErrorCode.EXECUTION_GRANT_INVALID,
                "The execution grant was rejected.",
            )

        try:
            self.validate_payload(request.action_payload)
        except (TypeError, ValueError) as exc:
            raise ToolInvocationError(
                ErrorCode.TOOL_EXECUTION_FAILED,
                "The tool payload is invalid.",
            ) from exc

        result = self.execute(request.action_payload)

        return {
            "success": True,
            "tool_name": self.tool_name,
            "execution_id": str(request.execution_id),
            "action_id": str(request.action_id),
            "output": result,
        }
