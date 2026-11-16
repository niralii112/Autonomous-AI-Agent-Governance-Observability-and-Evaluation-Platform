#!/usr/bin/env python3
"""Contract compatibility checks (spec sections 12 and 23.1).

    python scripts/check_contracts.py            # report; exit 1 only if a check FAILS
    python scripts/check_contracts.py --strict   # also exit 1 if any check is SKIPPED or WARNS

It reads the code with `ast` and the contract files with PyYAML/Pydantic. It never starts the app, never needs a
database and needs no environment variables, so it runs the same on a laptop and in CI.

Checks
  1. openapi       contracts/openapi.yaml is well formed: every operation has a unique operationId and x-endpoint-id.
  2. endpoints     every (method, path, operationId) of the contract is served by the routers, and nothing else is.
  3. enums         every enum of openapi.yaml equals the class of the same name in backend/app/core/enums.py.
  4. schemas       every schema of openapi.yaml exists in app.schemas with the same field names and required-ness.
  5. examples      every contracts/examples/<ENDPOINT-ID>.request|response*.json validates against its schema.
  6. signatures    the canonical functions of spec section 12: module, async-ness and parameter names.
  7. env           .env.example and Settings define the same environment variables.

Not covered here (separate commands): alembic check, schemathesis, npm run check:types, lint-imports.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OPENAPI = ROOT / "contracts" / "openapi.yaml"
EXAMPLES = ROOT / "contracts" / "examples"
HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# The canonical signatures of spec section 12: function -> (module, is_async, parameter names in order).
SIGNATURES: dict[str, tuple[str, bool, list[str]]] = {
    "register_agent": ("app/services/agent_service.py", True, ["session", "request", "actor"]),
    "register_tool": ("app/services/tool_service.py", True, ["session", "request", "actor"]),
    "create_policy": ("app/services/policy_service.py", True, ["session", "request", "actor"]),
    "evaluate_policy": ("app/services/policy_service.py", True, ["session", "request"]),
    "assess_risk": ("app/services/risk_service.py", True, ["request"]),
    "make_governance_decision": ("app/services/decision_service.py", False, ["request"]),
    "submit_action": ("app/services/action_service.py", True, ["session", "request", "actor"]),
    "request_human_approval": ("app/services/approval_service.py", True,
                               ["session", "action_id", "governance_decision_id", "payload_hash"]),
    "approve_action": ("app/services/approval_service.py", True, ["session", "approval_id", "request", "actor"]),
    "reject_action": ("app/services/approval_service.py", True, ["session", "approval_id", "request", "actor"]),
    "cancel_approval": ("app/services/approval_service.py", True, ["session", "approval_id", "actor"]),
    "execute_controlled_action": ("app/services/execution_service.py", True, ["session_factory", "execution_id"]),
    "record_execution_result": ("app/services/execution_service.py", True, ["session", "execution_id", "outcome"]),
    "evaluate_agent_performance": ("app/services/evaluation_service.py", True,
                                   ["session", "agent_id", "window_start", "window_end"]),
    "record_audit_event": ("app/services/audit_service.py", True, ["session", "event"]),
    "get_action_history": ("app/services/action_service.py", True, ["session", "filters", "pagination", "actor"]),
    "get_trace_details": ("app/services/trace_service.py", True, ["trace_id"]),
    "retry_action": ("app/services/action_service.py", True, ["session", "action_id", "actor"]),
    "expire_pending_approvals": ("app/services/background.py", True, ["session_factory"]),
    "reconcile_stale_executions": ("app/services/background.py", True, ["session_factory"]),
    "compute_payload_hash": ("app/core/hashing.py", False, ["action_payload"]),
    "mint_execution_grant": ("app/core/execution_grant.py", False,
                             ["execution_id", "action_id", "tool_name", "payload_hash"]),
}

# Environment variables that exist only for Docker or the frontend: allowed in .env.example without being a
# backend concern, and allowed in Settings without being listed twice.
ENV_ONLY_IN_FILE_OK: set[str] = set()


class Result:
    def __init__(self, name: str):
        self.name, self.status, self.problems, self.notes = name, "PASS", [], []

    def fail(self, message: str) -> None:
        self.status = "FAIL"
        self.problems.append(message)

    def warn(self, message: str) -> None:
        if self.status == "PASS":
            self.status = "WARN"
        self.problems.append(message)

    def skip(self, message: str) -> None:
        if self.status == "PASS":
            self.status = "SKIP"
        self.problems.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def load_spec() -> dict:
    return yaml.safe_load(OPENAPI.read_text(encoding="utf-8-sig"))


def operations(spec: dict):
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method in item:
                yield method.upper(), path, item[method]


# ------------------------------------------------------------------------------------------ 1. openapi

def check_openapi(spec: dict) -> Result:
    r = Result("openapi")
    ops = list(operations(spec))
    seen_ids: dict[str, str] = {}
    seen_endpoint_ids: dict[str, str] = {}
    for method, path, op in ops:
        label = f"{method} {path}"
        for key, seen in (("operationId", seen_ids), ("x-endpoint-id", seen_endpoint_ids)):
            value = op.get(key)
            if not value:
                r.fail(f"{label}: missing {key}")
            elif value in seen:
                r.fail(f"{label}: {key} {value} is also used by {seen[value]}")
            else:
                seen[value] = label
        if not any(str(code).startswith("2") for code in op.get("responses", {})):
            r.fail(f"{label}: no 2xx response")
    r.note(f"{len(ops)} operations, {len(spec.get('components', {}).get('schemas', {}))} schemas")
    return r


# ------------------------------------------------------------------------------------------ 2. endpoints

def _const(node: ast.AST):
    return node.value if isinstance(node, ast.Constant) else None


def _router_prefixes_and_routes(tree: ast.Module) -> tuple[dict[str, str], list[tuple[str, str, str | None]]]:
    """({router variable: prefix}, [(method, path, operation_id)]) of a router module."""
    prefixes: dict[str, str] = {}
    routes: list[tuple[str, str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if getattr(func, "id", None) == "APIRouter":
                prefix = next((_const(k.value) for k in node.value.keywords if k.arg == "prefix"), "") or ""
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = prefix
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for deco in node.decorator_list:
            if (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                    and isinstance(deco.func.value, ast.Name) and deco.func.attr in HTTP_METHODS):
                path = _const(deco.args[0]) if deco.args else None
                if path is None:
                    path = next((_const(k.value) for k in deco.keywords if k.arg == "path"), "")
                op_id = next((_const(k.value) for k in deco.keywords if k.arg == "operation_id"), None)
                routes.append((deco.func.attr.upper(), f"{deco.func.value.id}|{path}", op_id))
    return prefixes, routes


def served_endpoints() -> tuple[set[tuple[str, str, str | None]], list[str]]:
    """What the routers serve, from main.py's include_router calls and the router modules (no app import)."""
    problems: list[str] = []
    main = ast.parse((BACKEND / "app" / "main.py").read_text(encoding="utf-8-sig"))
    imports: dict[str, str] = {}  # alias -> module file
    for node in ast.walk(main):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.api"):
            for alias in node.names:
                imports[alias.asname or alias.name] = node.module
    served: set[tuple[str, str, str | None]] = set()
    for node in ast.walk(main):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router"
                and node.args and isinstance(node.args[0], ast.Name)):
            alias = node.args[0].id
            include_prefix = next((_const(k.value) for k in node.keywords if k.arg == "prefix"), "") or ""
            module = imports.get(alias)
            if module is None:
                problems.append(f"include_router({alias}): not imported from app.api")
                continue
            file = BACKEND / (module.replace(".", "/") + ".py")
            tree = ast.parse(file.read_text(encoding="utf-8-sig"))
            prefixes, routes = _router_prefixes_and_routes(tree)
            for method, tagged, op_id in routes:
                var, path = tagged.split("|", 1)
                full = include_prefix + prefixes.get(var, "") + path
                served.add((method, full, op_id))
    return served, problems


def check_endpoints(spec: dict) -> Result:
    r = Result("endpoints")
    contract = {(m, p, op.get("operationId")) for m, p, op in operations(spec)}
    served, problems = served_endpoints()
    for p in problems:
        r.fail(p)
    base = (spec.get("servers") or [{}])[0].get("url", "")
    base = base if base.startswith("/") else ""  # e.g. "/api/v1" when the contract paths are relative to it
    contract = {(m, base + p, i) for m, p, i in contract}

    def norm(path: str) -> str:  # parameter names do not matter, only the shape
        return re.sub(r"\{[^}]*\}", "{}", path)

    c_by_key = {(m, norm(p)): (p, i) for m, p, i in contract}
    s_by_key = {(m, norm(p)): (p, i) for m, p, i in served}
    for key in sorted(c_by_key.keys() - s_by_key.keys()):
        r.fail(f"in the contract but not served: {key[0]} {c_by_key[key][0]} ({c_by_key[key][1]})")
    for key in sorted(s_by_key.keys() - c_by_key.keys()):
        r.fail(f"served but not in the contract: {key[0]} {s_by_key[key][0]} ({s_by_key[key][1]})")
    for key in sorted(c_by_key.keys() & s_by_key.keys()):
        want, got = c_by_key[key][1], s_by_key[key][1]
        if want != got:
            r.fail(f"{key[0]} {c_by_key[key][0]}: operation_id is {got!r}, the contract says {want!r}")
    r.note(f"{len(c_by_key)} contract operations, {len(s_by_key)} served")
    return r


# ------------------------------------------------------------------------------------------ 3. enums

def enum_classes() -> dict[str, list[str]]:
    tree = ast.parse((BACKEND / "app" / "core" / "enums.py").read_text(encoding="utf-8-sig"))
    found: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            values = [_const(s.value) for s in node.body if isinstance(s, ast.Assign) and _const(s.value) is not None]
            if values:
                found[node.name] = values
    return found


def check_enums(spec: dict) -> Result:
    r = Result("enums")
    code = enum_classes()
    contract = {name: s["enum"] for name, s in spec["components"]["schemas"].items() if "enum" in s}
    for name, values in sorted(contract.items()):
        if name not in code:
            r.fail(f"{name}: in openapi.yaml but not in core/enums.py")
        elif set(values) != set(code[name]):
            r.fail(f"{name}: openapi-only {sorted(set(values) - set(code[name]))}, "
                   f"code-only {sorted(set(code[name]) - set(values))}")
        elif list(values) != list(code[name]):
            r.warn(f"{name}: same values, different order")
    r.note(f"{len(contract)} enums compared")
    enums_yaml = ROOT / "contracts" / "enums" / "enums.yaml"
    if enums_yaml.exists():
        listed = yaml.safe_load(enums_yaml.read_text(encoding="utf-8-sig"))
        for name, values in (listed.get("enums", listed) or {}).items():
            if name in contract and set(values) != set(contract[name]):
                r.fail(f"{name}: contracts/enums/enums.yaml differs from openapi.yaml")
    else:
        r.note("contracts/enums/enums.yaml is not in the repository (openapi.yaml and enums.py were compared)")
    return r


# ------------------------------------------------------------------------------------------ 4. schemas

def _load_schema_module():
    sys.path.insert(0, str(BACKEND))
    import app.schemas as schemas  # noqa: PLC0415 - needs only pydantic, no settings and no database

    return schemas


def check_schemas(spec: dict) -> Result:
    r = Result("schemas")
    try:
        schemas = _load_schema_module()
    except Exception as exc:  # noqa: BLE001
        r.fail(f"app.schemas could not be imported: {type(exc).__name__}: {exc}")
        return r
    checked = 0
    for name, schema in sorted(spec["components"]["schemas"].items()):
        if "enum" in schema or schema.get("type") != "object" or "properties" not in schema:
            continue
        model = getattr(schemas, name, None)
        if model is None:
            r.fail(f"{name}: in openapi.yaml but not in app.schemas")
            continue
        checked += 1
        want, got = set(schema["properties"]), set(model.model_fields)
        if want != got:
            r.fail(f"{name}: openapi-only fields {sorted(want - got)}, code-only fields {sorted(got - want)}")
            continue
        required = set(schema.get("required", []))
        code_required = {f for f, info in model.model_fields.items() if info.is_required()}
        if required != code_required:
            r.fail(f"{name}: required differs (contract-only {sorted(required - code_required)}, "
                   f"code-only {sorted(code_required - required)})")
    r.note(f"{checked} object schemas compared")
    return r


# ------------------------------------------------------------------------------------------ 5. examples

def _schema_name(node: dict | None) -> str | None:
    if not node:
        return None
    ref = node.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    if node.get("type") == "array" and "items" in node:
        return None
    return None


def check_examples(spec: dict) -> Result:
    r = Result("examples")
    try:
        schemas = _load_schema_module()
    except Exception as exc:  # noqa: BLE001
        r.skip(f"app.schemas could not be imported: {type(exc).__name__}: {exc}")
        return r
    by_endpoint = {op.get("x-endpoint-id"): op for _, _, op in operations(spec)}
    checked = skipped = 0
    for file in sorted(EXAMPLES.glob("*.json")):
        m = re.match(r"^([A-Z]+-\d+)\.(request|response)(?:\..+)?\.json$", file.name)
        if not m:
            skipped += 1
            continue
        endpoint_id, kind = m.group(1), m.group(2)
        op = by_endpoint.get(endpoint_id)
        if op is None:
            r.fail(f"{file.name}: no endpoint with x-endpoint-id {endpoint_id}")
            continue
        if kind == "request":
            node = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        else:
            ok = next((c for c in ("200", "201") if c in op["responses"]), None)  # 204 has no body: skipped
            node = op["responses"][ok].get("content", {}).get("application/json", {}).get("schema") if ok else None
        name = _schema_name(node)
        model = getattr(schemas, name, None) if name else None
        if model is None:
            skipped += 1
            continue
        try:
            model.model_validate(json.loads(file.read_text(encoding="utf-8-sig")))
            checked += 1
        except Exception as exc:  # noqa: BLE001
            first = str(exc).strip().splitlines()
            r.fail(f"{file.name} does not validate as {name}: {first[0]} {first[1] if len(first) > 1 else ''}".strip())
    r.note(f"{checked} examples validated, {skipped} skipped (no JSON body schema or not an endpoint example)")
    return r


# ------------------------------------------------------------------------------------------ 6. signatures

def check_signatures() -> Result:
    r = Result("signatures")
    for name, (module, is_async, params) in sorted(SIGNATURES.items()):
        file = BACKEND / module
        if not file.exists():
            r.fail(f"{name}: {module} does not exist")
            continue
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        fn = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
        if fn is None:
            r.fail(f"{name}: not defined in {module}")
            continue
        got = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        if isinstance(fn, ast.AsyncFunctionDef) != is_async:
            r.fail(f"{name}: should be {'async' if is_async else 'sync'}")
        if got != params:
            r.fail(f"{name}: parameters are {got}, the spec says {params}")
    r.note(f"{len(SIGNATURES)} functions compared")
    return r


# ------------------------------------------------------------------------------------------ 7. env

def settings_fields() -> set[str]:
    tree = ast.parse((BACKEND / "app" / "core" / "config.py").read_text(encoding="utf-8-sig"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings")
    return {n.target.id.upper() for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}


def check_env() -> Result:
    r = Result("env")
    example = ROOT / ".env.example"
    if not example.exists():
        r.fail(".env.example does not exist")
        return r
    keys = {line.split("=", 1)[0].strip() for line in example.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "=" in line}
    fields = settings_fields()
    for name in sorted(fields - keys):
        r.fail(f"{name}: defined in Settings but missing from .env.example")
    for name in sorted(keys - fields - ENV_ONLY_IN_FILE_OK):
        r.fail(f"{name}: in .env.example but not defined in Settings")
    placeholder = re.compile(r"^(JWT_SECRET_KEY|EXECUTION_GRANT_SECRET|POSTGRES_PASSWORD|SEED_\w+_PASSWORD)=(.+)$", re.M)
    for name, value in placeholder.findall(example.read_text(encoding="utf-8-sig")):
        if not re.search(r"change|example|placeholder|todo", value, re.I):
            r.warn(f"{name}: the value in .env.example does not look like a placeholder")
    r.note(f"{len(fields)} Settings fields, {len(keys)} variables in .env.example")
    return r


# ------------------------------------------------------------------------------------------ main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="a skipped check or a warning is also a failure")
    args = parser.parse_args()

    spec = load_spec()
    results = [check_openapi(spec), check_endpoints(spec), check_enums(spec), check_schemas(spec),
               check_examples(spec), check_signatures(), check_env()]
    for res in results:
        print(f"{res.status:5} {res.name}" + (f"  ({'; '.join(res.notes)})" if res.notes else ""))
        for problem in res.problems:
            print(f"        - {problem}")
    counts = {s: sum(1 for x in results if x.status == s) for s in ("PASS", "WARN", "SKIP", "FAIL")}
    print(f"\n{counts['PASS']} passed, {counts['WARN']} warnings, {counts['SKIP']} skipped, {counts['FAIL']} failed")
    bad = counts["FAIL"] or (args.strict and (counts["SKIP"] or counts["WARN"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
