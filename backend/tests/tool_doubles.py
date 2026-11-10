"""A test double that follows Student 2's real tool design (app/tools/base.py):
  - invoke() is a plain `def`, not async
  - the grant verifier is passed in when the tool is built
  - failures are raised as ToolInvocationError(error_code, message)
  - success returns a dict {"success": True, ..., "output": {...}}
"""

import time

from app.core.enums import ErrorCode


class ToolInvocationError(RuntimeError):
    def __init__(self, error_code, message):
        super().__init__(message)
        self.error_code = error_code


class StudentStyleTool:
    def __init__(self, tool_name, grant_verifier=None, behaviour="ok", delay=0.0):
        self.tool_name, self._grant_verifier, self.behaviour, self.delay = tool_name, grant_verifier, behaviour, delay
        self.calls = []

    def invoke(self, request, grant):
        if request.tool_name != self.tool_name:
            raise ToolInvocationError(ErrorCode.TOOL_NOT_AVAILABLE, "The requested tool does not match this tool instance.")
        if (grant.execution_id != request.execution_id or grant.action_id != request.action_id
                or grant.tool_name != request.tool_name):
            raise ToolInvocationError(ErrorCode.EXECUTION_GRANT_INVALID, "The execution grant does not match the invocation.")
        if self._grant_verifier is None:
            raise ToolInvocationError(ErrorCode.EXECUTION_GRANT_INVALID, "No execution-grant verifier is configured.")
        try:
            authorized = self._grant_verifier(grant, request)
        except Exception as exc:
            raise ToolInvocationError(ErrorCode.EXECUTION_GRANT_INVALID, "Execution-grant verification failed.") from exc
        if authorized is not True:
            raise ToolInvocationError(ErrorCode.EXECUTION_GRANT_INVALID, "The execution grant was rejected.")

        self.calls.append(request)
        if self.behaviour == "invalid_payload":
            raise ToolInvocationError(ErrorCode.TOOL_EXECUTION_FAILED, "The tool payload is invalid.")
        if self.behaviour == "crash":
            raise RuntimeError("boom: secret internal detail")
        if self.behaviour == "slow":
            time.sleep(self.delay)
        if self.behaviour == "bad_result":
            return "oops"
        if self.behaviour == "dict_failure":
            return {"success": False, "error_code": "TOOL_EXECUTION_FAILED", "error_message": "declined"}
        return {"success": True, "tool_name": self.tool_name, "execution_id": str(request.execution_id),
                "action_id": str(request.action_id), "output": {"simulated": True}}
