"""Generate backend/app/schemas/*.py from contracts/openapi.yaml.

Run from the repo root:  python backend/scripts/generate_schemas.py
The generated files say "do not edit by hand". If the contract changes, run this again.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "contracts" / "openapi.yaml"
OUT = ROOT / "backend" / "app" / "schemas"

# Which module each schema lives in (spec section 7, file table). One exception: see MOVED.
MODULES = {
    "common": ["ErrorResponse", "ErrorDetail", "ActorContext", "PaginationParams"],
    "auth": ["LoginRequest", "TokenResponse"],
    "user": ["UserCreateRequest", "UserResponse", "UserResponsePage", "UserUpdateRequest"],
    "agent": ["AgentCreateRequest", "AgentResponse", "AgentResponsePage", "AgentUpdateRequest",
              "ToolPermissionItem", "ToolPermissionListResponse", "ToolPermissionResponse",
              "ToolPermissionsUpdateRequest"],
    "tool": ["ToolCreateRequest", "ToolResponse", "ToolResponsePage", "ToolUpdateRequest"],
    "policy": ["PolicyActivationRequest", "PolicyCondition", "PolicyConditions",
               "PolicyCreateRequest", "PolicyEvaluationRequest", "PolicyEvaluationResponse",
               "PolicyResponse", "PolicyResponsePage", "PolicyVersionCreateRequest",
               "MatchedPolicy"],
    "action": ["ActionSubmissionRequest", "ActionResponse",
               "ActionSummary", "ActionSummaryPage", "ActionHistoryFilter"],
    # MOVED: ActionSubmissionResponse and ActionDetailResponse live here (not in action.py)
    # to avoid a circular import between action.py and approval.py (ApprovalResponse uses
    # ActionSummary). action.py still exposes both through __getattr__.
    "action_detail": ["ActionSubmissionResponse", "ActionDetailResponse"],
    "action_payloads": ["FinanceGetReportPayload", "FinanceGenerateSummaryPayload",
                        "FinanceProposePaymentPayload", "FinanceAccessSensitiveRecordsPayload",
                        "SupportGetTicketPayload", "SupportGenerateResponsePayload",
                        "SupportProposeRefundPayload", "SupportAccessCustomerInfoPayload",
                        "ItGetServerStatusPayload", "ItAnalyzeLogsPayload",
                        "ItRestartServerPayload", "ItChangePrivilegedConfigPayload",
                        "ActionPayload"],
    "decision": ["GovernanceDecisionOutcome", "GovernanceDecisionRequest",
                 "GovernanceDecisionResponse", "GovernanceDecisionResponsePage"],
    "approval": ["ApprovalDecisionResponse", "ApprovalRejectRequest", "ApprovalResponse",
                 "ApprovalResponsePage", "ApprovalReviewRequest"],
    "execution": ["ExecutionOutcome", "ExecutionResponse", "ExecutionResponsePage"],
    "audit": ["AuditEventCreate", "AuditEventResponse", "AuditEventResponsePage"],
    "tool_runtime": ["ExecutionGrant", "ToolInvocationRequest", "ToolInvocationResult"],
    "risk": ["RiskContext", "RiskAssessmentRequest", "RiskAssessmentResponse",
             "RiskAssessmentResponsePage", "RiskSummaryResponse", "ModelVersionResponse",
             "ModelVersionResponsePage", "RiskLevelCount", "RiskSourceCount", "ScoreBucket"],
    "evaluation": ["EvaluationResultResponse", "EvaluationResultResponsePage",
                   "EvaluationRunRequest", "ProductionMetrics", "LabelledMetrics",
                   "OverviewMetricsResponse", "AgentPerformanceResponse", "ConfusionMatrix",
                   "CategoryMetric", "TimeBucketCount"],
    "agent_run": ["AgentScenario", "AgentScenarioListResponse", "AgentRunRequest",
                  "AgentRunResponse"],
    "trace": ["SpanDetail", "TraceByActionResponse", "TraceDetailResponse",
              "TraceMetricsBucket", "TraceMetricsResponse", "TraceSummary", "TraceSummaryPage"],
    "system": ["HealthResponse", "ComponentHealth", "SystemInfoResponse"],
}

spec = yaml.safe_load(SPEC.read_text())
SCHEMAS = spec["components"]["schemas"]
ENUMS = {n for n, s in SCHEMAS.items() if "enum" in s}
MODULE_OF = {n: m for m, names in MODULES.items() for n in names}
stats = {"optional_without_default": []}


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


class Ctx:
    """Collects the imports one module needs."""

    def __init__(self, module: str):
        self.module = module
        self.enums: set[str] = set()
        self.cross: dict[str, set[str]] = {}
        self.uses_any = self.uses_uuid = self.uses_datetime = self.uses_literal = False

    def use_ref(self, name: str) -> str:
        if name in ENUMS:
            self.enums.add(name)
        elif MODULE_OF[name] != self.module:
            self.cross.setdefault(MODULE_OF[name], set()).add(name)
        return name


def py_type(s: dict, ctx: Ctx) -> str:
    """Return the Python type expression for an OpenAPI schema node."""
    if "$ref" in s:
        return ctx.use_ref(ref_name(s["$ref"]))
    if "allOf" in s and len(s["allOf"]) == 1:
        return py_type(s["allOf"][0], ctx)
    if "anyOf" in s:
        parts = [py_type(x, ctx) for x in s["anyOf"] if x.get("type") != "null"]
        nullable = any(x.get("type") == "null" for x in s["anyOf"])
        out = " | ".join(parts)
        return f"{out} | None" if nullable else out
    if "const" in s:
        ctx.uses_literal = True
        return f"Literal[{s['const']!r}]"
    t = s.get("type")
    if t == "string":
        fmt = s.get("format")
        if fmt == "uuid":
            ctx.uses_uuid = True
            return "UUID"
        if fmt == "date-time":
            ctx.uses_datetime = True
            return "datetime"
        return "str"
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "array":
        return f"list[{py_type(s['items'], ctx)}]"
    if t == "object":
        ap = s.get("additionalProperties")
        if isinstance(ap, dict) and ap:
            return f"dict[str, {py_type(ap, ctx)}]"
        ctx.uses_any = True
        return "dict[str, Any]"
    if not s:  # {} means "any value"
        ctx.uses_any = True
        return "Any"
    raise ValueError(f"unsupported schema node: {s}")


def constraints(s: dict) -> list[str]:
    node = s
    if "anyOf" in s:  # constraints sit on the non-null branch
        node = next((x for x in s["anyOf"] if x.get("type") != "null"), {})
    out = []
    for key, arg in (("minimum", "ge"), ("maximum", "le"), ("minLength", "min_length"),
                     ("maxLength", "max_length"), ("pattern", "pattern")):
        if key in node:
            out.append(f"{arg}={node[key]!r}")
    return out


def default_expr(s: dict, tp: str) -> str | None:
    if "default" not in s:
        return None
    d = s["default"]
    if d == []:
        return "default_factory=list"
    if d == {}:
        return "default_factory=dict"
    base = tp.split(" | ")[0]
    if base in ENUMS:
        return f"default={base}({d!r})"
    return f"default={d!r}"


def gen_model(name: str, ctx: Ctx) -> str:
    s = SCHEMAS[name]
    required = set(s.get("required", []))
    cfg = ["from_attributes=True", "protected_namespaces=()"]
    if s.get("additionalProperties") is False:
        cfg.insert(0, 'extra="forbid"')
    lines = [f"class {name}(BaseModel):"]
    if s.get("description"):
        lines.append(f'    """{s["description"]}"""')
        lines.append("")
    lines.append(f"    model_config = ConfigDict({', '.join(cfg)})")
    lines.append("")
    for prop, ps in s.get("properties", {}).items():
        tp = py_type(ps, ctx)
        parts = constraints(ps)
        dflt = default_expr(ps, tp)
        if prop in required:
            if dflt:
                parts.insert(0, dflt)
            elif not parts:
                lines.append(f"    {prop}: {tp}")
                continue
            else:
                parts.insert(0, "...")
        else:
            if dflt:
                parts.insert(0, dflt)
            else:
                if "None" not in tp.split(" | "):
                    tp = f"{tp} | None"
                    stats["optional_without_default"].append(f"{name}.{prop}")
                parts.insert(0, "default=None")
        lines.append(f"    {prop}: {tp} = Field({', '.join(parts)})")
    return "\n".join(lines)


def deps(name: str) -> set[str]:
    found: set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "$ref":
                    found.add(ref_name(v))
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(SCHEMAS[name])
    return found


def order(names: list[str]) -> list[str]:
    done, out = set(), []

    def visit(n):
        if n in done:
            return
        done.add(n)
        for d in sorted(deps(n)):
            if d in names:
                visit(d)
        out.append(n)

    for n in names:
        visit(n)
    return out


def camel_to_upper_snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).upper()


FOOTERS = {
    "common": '''

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic page envelope (spec: Page[T]). The contract's concrete *Page classes have the same shape."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
''',
    "action": '''

def __getattr__(name: str):
    """ActionSubmissionResponse and ActionDetailResponse live in action_detail.py (avoids a
    circular import). This keeps `from app.schemas.action import ActionSubmissionResponse` working."""
    if name in ("ActionSubmissionResponse", "ActionDetailResponse"):
        from app.schemas import action_detail

        return getattr(action_detail, name)
    raise AttributeError(name)
''',
}


def build_module(module: str) -> str:
    ctx = Ctx(module)
    names = order(MODULES[module])
    body: list[str] = []
    for n in names:
        s = SCHEMAS[n]
        if "oneOf" in s:  # ActionPayload: a union of the 12 payload models
            members = [ref_name(x["$ref"]) for x in s["oneOf"]]
            body.append(f"ActionPayload = Union[{', '.join(members)}]")
            body.append("")
            body.append("# ActionType -> payload model (spec: ACTION_PAYLOAD_MODELS)")
            ctx.enums.add("ActionType")
            rows = [f"    ActionType.{camel_to_upper_snake(m.removesuffix('Payload'))}: {m},"
                    for m in members]
            body.append("ACTION_PAYLOAD_MODELS: dict[ActionType, type[BaseModel]] = {")
            body.extend(rows)
            body.append("}")
        else:
            body.append(gen_model(n, ctx))
        body.append("")
        body.append("")
    head = [
        f'"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.',
        f'',
        f'Module: app.schemas.{module}',
        '"""',
        "",
    ]
    std = []
    if ctx.uses_datetime:
        std.append("from datetime import datetime")
    if any(" Union[" in b or b.startswith("ActionPayload") for b in body):
        typing_names = ["Union"]
    else:
        typing_names = []
    if ctx.uses_any:
        typing_names.append("Any")
    if ctx.uses_literal:
        typing_names.append("Literal")
    if module == "common":
        typing_names += ["Generic", "TypeVar"]
    if typing_names:
        std.append(f"from typing import {', '.join(sorted(typing_names))}")
    if ctx.uses_uuid:
        std.append("from uuid import UUID")
    imports = std + [""] if std else []
    imports += ["from pydantic import BaseModel, ConfigDict, Field"]
    if ctx.enums:
        imports += ["", "from app.core.enums import (" ]
        imports += [f"    {e}," for e in sorted(ctx.enums)] + [")"]
    for m in sorted(ctx.cross):
        imports.append(f"from app.schemas.{m} import {', '.join(sorted(ctx.cross[m]))}")
    out = "\n".join(head + imports) + "\n\n\n" + "\n".join(body).rstrip() + "\n"
    return out + FOOTERS.get(module, "")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    covered = set(MODULE_OF) | ENUMS
    missing = set(SCHEMAS) - covered
    assert not missing, f"schemas without a module: {sorted(missing)}"
    all_names: dict[str, str] = {}
    for module in MODULES:
        (OUT / f"{module}.py").write_text(build_module(module))
        for n in MODULES[module]:
            all_names[n] = module
    lines = ['"""Re-exports every schema class (generated by scripts/generate_schemas.py)."""', ""]
    for module in MODULES:
        names = list(MODULES[module])
        if module == "action_payloads":
            names += ["ACTION_PAYLOAD_MODELS"]
        if module == "common":
            names += ["Page"]
        lines.append(f"from app.schemas.{module} import (")
        lines += [f"    {n}," for n in sorted(names)] + [")"]
    exported = sorted(list(all_names) + ["ACTION_PAYLOAD_MODELS", "Page"])
    lines += ["", "__all__ = ["] + [f'    "{n}",' for n in exported] + ["]"]
    (OUT / "__init__.py").write_text("\n".join(lines) + "\n")
    print(f"generated {len(MODULES)} modules, {len(all_names)} schema classes")
    print("optional fields without default (made `| None = None`):", stats["optional_without_default"])


if __name__ == "__main__":
    sys.exit(main())
