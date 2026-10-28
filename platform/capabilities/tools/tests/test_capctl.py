"""capctl catches the ways a generated capability can drift from its definition."""

import copy
import shutil
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import capctl  # noqa: E402

EXAMPLE = capctl.ROOT / "postgres-database"


@pytest.fixture
def definition():
    return yaml.safe_load((EXAMPLE / "capability.yaml").read_text())


@pytest.fixture
def xrd():
    return capctl.load_yaml_documents(EXAMPLE / "definition.yaml")[0]


@pytest.fixture
def folder(tmp_path):
    target = tmp_path / "postgres-database"
    shutil.copytree(EXAMPLE, target)
    return target


def test_the_example_is_consistent():
    assert capctl.validate(["postgres-database"], definition_only=False) == 0


def test_schema_rejects_an_incomplete_definition(definition):
    del definition["spec"]["acceptance"]
    assert any("acceptance" in e for e in capctl.definition_errors("postgres-database", definition))


def test_duplicate_ids_are_rejected(definition):
    definition["spec"]["acceptance"][1]["id"] = "AC-1"
    assert "The acceptance criterion id AC-1 is used more than once." in capctl.definition_errors("postgres-database", definition)


def test_cost_must_cover_every_size(definition):
    del definition["spec"]["guardrails"]["cost"]["large"]
    assert any("cost" in e for e in capctl.definition_errors("postgres-database", definition))


def test_xrd_must_keep_the_interface(definition, xrd):
    assert capctl.xrd_errors(definition, xrd) == []
    changed = copy.deepcopy(xrd)
    props = changed["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
    props["size"]["enum"] = ["small", "medium", "large", "xlarge"]
    props["replicas"] = {"type": "integer"}
    errors = capctl.xrd_errors(definition, changed)
    assert "Parameter 'size' must allow exactly ['small', 'medium', 'large'] in the XRD." in errors
    assert "The XRD has a parameter 'replicas' that the interface does not define." in errors


def test_xrd_annotations_must_match_the_definition(definition, xrd):
    definition["spec"]["guardrails"]["agents"][0]["rule"] = "Agents can create any database."
    assert any("guardrails does not match" in e for e in capctl.xrd_errors(definition, xrd))


def test_every_guardrail_needs_a_policy_and_a_test(definition, folder):
    policy = folder / "policy.yaml"
    policy.write_text(policy.read_text().replace("[GR-2]", "").replace("[GR-3] Human approval required:", "[GR-3]"))
    errors = capctl.guardrail_errors(definition, folder)
    assert any(e.startswith("GR-2 is not enforced") for e in errors)
    assert any(e.startswith("GR-3 needs human approval") for e in errors)


def test_every_criterion_needs_a_test(definition, folder):
    tests = folder / "tests" / "e2e" / "test_acceptance.py"
    tests.write_text(tests.read_text().replace("def test_ac_6_", "def test_cleanup_"))
    assert capctl.acceptance_errors(definition, folder) == [
        "AC-6 has no end-to-end test (a function named test_ac_6_...)."]
