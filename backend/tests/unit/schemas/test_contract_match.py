"""Check every generated schema class against contracts/openapi.yaml."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

import app.schemas as schemas

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC = yaml.safe_load((REPO_ROOT / "contracts" / "openapi.yaml").read_text())
ALL = SPEC["components"]["schemas"]
MODELS = {n: s for n, s in ALL.items() if "enum" not in s and "oneOf" not in s}

CONSTRAINT_KEYS = ("minimum", "maximum", "minLength", "maxLength")


def constraints_in(node: dict) -> dict:
    """Collect min/max constraints from a schema node, looking inside anyOf branches."""
    found = {k: node[k] for k in CONSTRAINT_KEYS if k in node}
    for branch in node.get("anyOf", []):
        found.update({k: branch[k] for k in CONSTRAINT_KEYS if k in branch})
    for branch in node.get("allOf", []):
        found.update({k: branch[k] for k in CONSTRAINT_KEYS if k in branch})
    return found


def test_contract_has_expected_size():
    assert len(ALL) == 126
    assert len(MODELS) == 103


@pytest.mark.parametrize("name", sorted(MODELS))
def test_class_exists_and_is_a_pydantic_model(name):
    cls = getattr(schemas, name)
    assert issubclass(cls, BaseModel)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_fields_match_contract_properties(name):
    cls = getattr(schemas, name)
    assert set(cls.model_fields) == set(MODELS[name].get("properties", {}))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_required_fields_match_contract(name):
    cls = getattr(schemas, name)
    required = {f for f, info in cls.model_fields.items() if info.is_required()}
    assert required == set(MODELS[name].get("required", []))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_extra_fields_are_forbidden_when_contract_says_so(name):
    cls = getattr(schemas, name)
    forbids = cls.model_config.get("extra") == "forbid"
    assert forbids == (MODELS[name].get("additionalProperties") is False)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_numeric_and_length_limits_match_contract(name):
    cls = getattr(schemas, name)
    json_props = cls.model_json_schema().get("properties", {})
    for prop, spec_node in MODELS[name].get("properties", {}).items():
        expected = constraints_in(spec_node)
        actual = constraints_in(json_props[prop])
        assert actual == expected, f"{name}.{prop}: {actual} != {expected}"


def test_enum_values_in_core_match_contract():
    from enum import Enum

    from app.core import enums

    for name, spec_node in ALL.items():
        if "enum" in spec_node:
            cls = getattr(enums, name)
            assert issubclass(cls, Enum)
            assert [m.value for m in cls] == spec_node["enum"], name


def test_generated_files_are_not_hand_edited():
    """Re-run the generator in memory and compare with the files on disk."""
    gen_path = Path(__file__).resolve().parents[3] / "scripts" / "generate_schemas.py"
    spec = importlib.util.spec_from_file_location("generate_schemas", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    schemas_dir = Path(schemas.__file__).parent
    for module in gen.MODULES:
        assert (schemas_dir / f"{module}.py").read_text() == gen.build_module(module), module
