"""Every sample request/response in contracts/examples must validate against our schemas."""

import json
from pathlib import Path

import pytest
import yaml

import app.schemas as schemas

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text())


def _ref(node):
    return node["$ref"].rsplit("/", 1)[-1] if isinstance(node, dict) and "$ref" in node else None


def _endpoint_schemas():
    """endpoint id (e.g. ACT-01) -> (request schema name, response schema name)."""
    out = {}
    for item in SPEC["paths"].values():
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            request = None
            if "requestBody" in op:
                request = _ref(op["requestBody"]["content"]["application/json"]["schema"])
            response = None
            for code in ("200", "201"):
                if code in op["responses"]:
                    body = op["responses"][code].get("content", {}).get("application/json", {})
                    response = _ref(body.get("schema"))
            out[op["x-endpoint-id"]] = (request, response)
    return out


ENDPOINTS = _endpoint_schemas()
EXAMPLES = sorted((CONTRACTS / "examples").glob("*.json"))
ERROR_EXAMPLES = sorted((CONTRACTS / "examples" / "errors").glob("*.json"))


def test_examples_were_found():
    assert len(EXAMPLES) == 75
    assert len(ERROR_EXAMPLES) == 29


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_endpoint_example_validates(path):
    endpoint_id, kind = path.name.split(".")[:2]
    request_name, response_name = ENDPOINTS[endpoint_id]
    class_name = request_name if kind == "request" else response_name
    assert class_name, f"{path.name}: no schema in the contract"
    getattr(schemas, class_name).model_validate(json.loads(path.read_text()))


@pytest.mark.parametrize("path", ERROR_EXAMPLES, ids=lambda p: p.name)
def test_error_example_validates(path):
    data = json.loads(path.read_text())
    schemas.ErrorResponse.model_validate(data)
    assert data["error_code"] == path.stem
