"""Checks platform capabilities against their definitions.

    python platform/capabilities/tools/capctl.py validate [NAME ...] [--definition-only]
    python platform/capabilities/tools/capctl.py trace NAME [--junit FILE] [--kyverno PASS|FAIL] [--render PASS|FAIL]

`validate` is the mechanical part of the review: the definition follows the
schema and, once an agent has built the capability, what it generated keeps
the contract (parameters, guardrails, acceptance criteria). `trace` writes
TRACEABILITY.md, the matrix the human reviewer reads: each acceptance
criterion with its tests and result, each guardrail with what enforces it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "capability-definition.schema.json"
GROUP = "platform.starterkit.dev"
PREFIX = "platform.starterkit.dev"
APPROVAL_MARKER = "Human approval required"

# What an agent must generate for every capability, relative to its folder.
GENERATED = {
    "definition.yaml": "the platform API (Crossplane XRD)",
    "composition.yaml": "how it is built (Crossplane Composition)",
    "policy.yaml": "the guardrails (Kyverno policies)",
    "tests/e2e/test_acceptance.py": "acceptance tests",
    "docs/index.md": "documentation (TechDocs)",
    "mkdocs.yml": "documentation (TechDocs)",
    "SKILL.md": "the skill that teaches agents to use it",
}


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def definition_path(name: str) -> Path:
    return ROOT / name / "capability.yaml"


def all_capabilities() -> list[str]:
    return sorted(p.parent.name for p in ROOT.glob("*/capability.yaml"))


# --- Definition --------------------------------------------------------------


def schema_errors(definition: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
    errors = []
    for error in sorted(validator.iter_errors(definition), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{where}: {error.message}")
    return errors


def definition_errors(name: str, definition: dict[str, Any]) -> list[str]:
    errors = schema_errors(definition)
    if errors:
        return errors
    spec = definition["spec"]
    if definition["metadata"]["name"] != name:
        errors.append(f"metadata.name is '{definition['metadata']['name']}' but the folder is '{name}'.")
    rules = spec["guardrails"]["everyone"] + spec["guardrails"]["agents"]
    for label, ids in (("guardrail", [r["id"] for r in rules]), ("acceptance criterion", [a["id"] for a in spec["acceptance"]])):
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            errors.append(f"The {label} id {dup} is used more than once.")
    params = spec["interface"]["parameters"]
    names = [p["name"] for p in params]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        errors.append(f"The parameter '{dup}' is defined more than once.")
    for p in params:
        if "default" in p and "enum" in p and p["default"] not in p["enum"]:
            errors.append(f"The default of parameter '{p['name']}' is not one of its allowed values.")
    cost = spec["guardrails"].get("cost")
    size = next((p for p in params if p["name"] == "size"), None)
    if cost and size and "enum" in size and set(cost) != set(size["enum"]):
        errors.append("guardrails.cost must give a cost for each size: " + ", ".join(size["enum"]) + ".")
    return errors


# --- What the agent generated -------------------------------------------------


def _typed(value: str, kind: str) -> Any:
    if kind == "integer":
        return int(value)
    if kind == "boolean":
        return value.lower() == "true"
    return value


def xrd_errors(definition: dict[str, Any], xrd: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    name = definition["metadata"]["name"]
    iface = definition["spec"]["interface"]
    spec = xrd.get("spec", {})
    if xrd.get("kind") != "CompositeResourceDefinition":
        return ["definition.yaml must be a CompositeResourceDefinition."]
    if spec.get("group") != GROUP:
        errors.append(f"The XRD group must be {GROUP}.")
    if spec.get("names", {}).get("kind") != iface["kind"]:
        errors.append(f"The XRD kind must be {iface['kind']}, as in interface.kind.")
    if spec.get("scope", "Namespaced") != iface["scope"]:
        errors.append(f"The XRD scope must be {iface['scope']}, as in interface.scope.")
    labels = xrd.get("metadata", {}).get("labels", {})
    if labels.get(f"{PREFIX}/capability") != name:
        errors.append(f"The XRD needs the label {PREFIX}/capability: {name}, so the portal and the MCP server find it.")
    errors += annotation_errors(definition, xrd.get("metadata", {}).get("annotations", {}))
    versions = spec.get("versions", [])
    if not versions:
        return errors + ["The XRD has no versions."]
    props = (
        versions[-1].get("schema", {}).get("openAPIV3Schema", {}).get("properties", {})
        .get("spec", {}).get("properties", {})
    )
    declared = {p["name"]: p for p in iface["parameters"]}
    for extra in sorted(set(props) - set(declared)):
        errors.append(f"The XRD has a parameter '{extra}' that the interface does not define.")
    for pname, p in declared.items():
        prop = props.get(pname)
        if prop is None:
            errors.append(f"The XRD is missing the parameter '{pname}'.")
            continue
        if prop.get("type") != p["type"]:
            errors.append(f"Parameter '{pname}' must be of type {p['type']} in the XRD.")
        if "enum" in p and [str(v) for v in prop.get("enum", [])] != p["enum"]:
            errors.append(f"Parameter '{pname}' must allow exactly {p['enum']} in the XRD.")
        if "default" in p and prop.get("default") != _typed(p["default"], p["type"]):
            errors.append(f"Parameter '{pname}' must default to {p['default']} in the XRD.")
        for bound in ("minimum", "maximum"):
            if bound in p and prop.get(bound) != p[bound]:
                errors.append(f"Parameter '{pname}' must have {bound} {p[bound]} in the XRD.")
    return errors


def annotation_errors(definition: dict[str, Any], annotations: dict[str, str]) -> list[str]:
    """The XRD carries what consumers need to choose and use it, copied from the definition."""
    spec = definition["spec"]
    expected = {
        "title": definition["metadata"]["title"],
        "owner": definition["metadata"]["owner"],
        "stage": spec.get("delivery", {}).get("stage", "experimental"),
        "description": spec["purpose"]["problem"],
        "guardrails": [r["rule"] for r in spec["guardrails"]["everyone"] + spec["guardrails"]["agents"]],
        "examples": spec["interface"].get("examples", []),
        "cost": spec["guardrails"].get("cost", {}),
        "outputs": spec["interface"]["outputs"],
    }
    errors = []
    for key, value in expected.items():
        raw = annotations.get(f"{PREFIX}/{key}")
        if raw is None:
            errors.append(f"The XRD needs the annotation {PREFIX}/{key}.")
            continue
        actual = raw if isinstance(value, str) else _json(raw)
        if actual != value:
            errors.append(f"The XRD annotation {PREFIX}/{key} does not match the definition.")
    return errors


def _json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return None


def composition_errors(definition: dict[str, Any], compositions: list[dict[str, Any]]) -> list[str]:
    kind = definition["spec"]["interface"]["kind"]
    refs = [c.get("spec", {}).get("compositeTypeRef", {}) for c in compositions if c.get("kind") == "Composition"]
    if not any(r.get("kind") == kind and r.get("apiVersion", "").startswith(f"{GROUP}/") for r in refs):
        return [f"composition.yaml has no Composition for {kind}."]
    return []


def guardrail_errors(definition: dict[str, Any], folder: Path) -> list[str]:
    errors = []
    policy = (folder / "policy.yaml").read_text()
    tests = "\n".join(p.read_text() for p in (folder / "tests" / "kyverno").rglob("*.yaml"))
    for scope in ("everyone", "agents"):
        for rule in definition["spec"]["guardrails"][scope]:
            rid = rule["id"]
            if f"[{rid}]" not in policy:
                errors.append(f"{rid} is not enforced: no policy message in policy.yaml starts with [{rid}].")
            elif rule["enforcement"] == "approval" and not re.search(rf"\[{rid}\][^\n]*{APPROVAL_MARKER}", policy):
                errors.append(f"{rid} needs human approval: its message must say '{APPROVAL_MARKER}' so agents get an approval request.")
            if rid not in tests:
                errors.append(f"{rid} has no policy test in tests/kyverno.")
    return errors


def acceptance_tests(folder: Path) -> dict[str, list[str]]:
    """Maps AC-n to the test functions named test_ac_n_*."""
    source = (folder / "tests" / "e2e" / "test_acceptance.py").read_text()
    found: dict[str, list[str]] = {}
    for match in re.finditer(r"^def (test_ac_(\d+)_\w+)", source, re.MULTILINE):
        found.setdefault(f"AC-{match.group(2)}", []).append(match.group(1))
    return found


def acceptance_errors(definition: dict[str, Any], folder: Path) -> list[str]:
    tests = acceptance_tests(folder)
    ids = {a["id"] for a in definition["spec"]["acceptance"]}
    errors = [f"{ac} has no end-to-end test (a function named test_{ac.lower().replace('-', '_')}_...)." for ac in sorted(ids - set(tests))]
    errors += [f"{ac} has tests but is not in the definition." for ac in sorted(set(tests) - ids)]
    return errors


def generated_errors(name: str, definition: dict[str, Any]) -> list[str]:
    folder = ROOT / name
    missing = [f"{path} is missing ({what})." for path, what in GENERATED.items() if not (folder / path).exists()]
    if not list((folder / "tests" / "kyverno").rglob("kyverno-test.yaml")):
        missing.append("tests/kyverno/ needs at least one kyverno-test.yaml (policy tests).")
    if not list((folder / "examples").glob("*.yaml")):
        missing.append("examples/ needs at least one request, used to render the composition.")
    if missing:
        return missing
    errors = xrd_errors(definition, load_yaml_documents(folder / "definition.yaml")[0])
    errors += composition_errors(definition, load_yaml_documents(folder / "composition.yaml"))
    errors += guardrail_errors(definition, folder)
    errors += acceptance_errors(definition, folder)
    return errors


def validate(names: list[str], definition_only: bool) -> int:
    failed = False
    for name in names or all_capabilities():
        path = definition_path(name)
        if not path.exists():
            print(f"✗ {name}: {path.relative_to(ROOT.parent)} does not exist")
            failed = True
            continue
        definition = yaml.safe_load(path.read_text())
        errors = definition_errors(name, definition)
        built = (ROOT / name / "definition.yaml").exists()
        if not errors and not definition_only and built:
            errors = generated_errors(name, definition)
        state = "definition" if definition_only or not built else "definition and generated files"
        if errors:
            failed = True
            print(f"✗ {name} ({state})")
            for error in errors:
                print(f"    - {error}")
        else:
            print(f"✓ {name} ({state})")
    return 1 if failed else 0


# --- Traceability -------------------------------------------------------------


def junit_results(path: Path | None) -> dict[str, str]:
    """Test function name (with parameters) -> passed, failed or skipped."""
    if path is None or not path.exists():
        return {}
    results = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        outcome = "passed"
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        results[case.get("name", "")] = outcome
    return results


def _mark(outcome: str | None) -> str:
    return {"passed": "✅ passed", "PASS": "✅ passed", "failed": "❌ failed", "FAIL": "❌ failed",
            "skipped": "⚠️ skipped"}.get(outcome or "", "⏳ not run")


def trace(name: str, junit: Path | None, kyverno: str | None, render: str | None) -> int:
    folder = ROOT / name
    definition = yaml.safe_load(definition_path(name).read_text())
    spec = definition["spec"]
    results = junit_results(junit)
    tests = acceptance_tests(folder)
    policy_docs = load_yaml_documents(folder / "policy.yaml")
    lines = [
        f"# Traceability: {definition['metadata']['title']}",
        "",
        f"Generated by `capctl trace` from [`capability.yaml`](capability.yaml). "
        "Each acceptance criterion maps to its end-to-end tests and each guardrail to the policy that enforces it.",
        "",
        "## Acceptance criteria",
        "",
        "| Id | Criterion | Checked as | Tests | Result |",
        "|---|---|---|---|---|",
    ]
    failed = False
    for ac in spec["acceptance"]:
        criterion = " ".join(s for s in (
            f"Given {ac['given']}," if ac.get("given") else "", f"when {ac['when']},", f"then {ac['then']}.") if s)
        names = tests.get(ac["id"], [])
        runs = {k: v for k, v in results.items() if any(k == n or k.startswith(n + "[") for n in names)}
        if not runs:
            outcome = None
        elif any(v == "failed" for v in runs.values()):
            outcome, failed = "failed", True
        else:
            outcome = "passed" if all(v == "passed" for v in runs.values()) else "skipped"
        if ac.get("as", "both") == "both" and runs and not (
            any("human" in k for k in runs) and any("agent" in k for k in runs)):
            outcome, failed = "failed", True
            names = names + ["(must run as a human and as an agent)"]
        shown = ", ".join(f"`{k}`" for k in sorted(runs)) or ", ".join(f"`{n}`" for n in names) or "—"
        lines.append(f"| {ac['id']} | {criterion} | {ac.get('as', 'both')} | {shown} | {_mark(outcome)} |")

    lines += ["", "## Guardrails", "", "| Id | Rule | Applies to | Enforcement | Enforced by | Policy tests |", "|---|---|---|---|---|---|"]
    for scope, who in (("everyone", "everyone"), ("agents", "agents")):
        for rule in spec["guardrails"][scope]:
            enforcer = next((
                f"`{d['metadata']['name']}`" for d in policy_docs if f"[{rule['id']}]" in yaml.safe_dump(d)), "—")
            lines.append(f"| {rule['id']} | {rule['rule']} | {who} | {rule['enforcement']} | {enforcer} | {_mark(kyverno)} |")

    lines += ["", "## Interface", "", f"`{spec['interface']['kind']}` ({spec['interface']['scope']}), "
              f"composition rendered: {_mark(render)}", "", "| Parameter | Type | Allowed values | Default |", "|---|---|---|---|"]
    for p in spec["interface"]["parameters"]:
        lines.append(f"| {p['name']} | {p['type']} | {', '.join(p.get('enum', [])) or '—'} | {p.get('default', '—')} |")
    lines += ["", "## For the reviewer", "", "CI checked everything above. What only a person can judge:", "",
              "- [ ] The interface makes sense to the teams that will use it.",
              "- [ ] The composition is reasonable to operate (resources, storage, upgrades).",
              "- [ ] The estimated cost is realistic.",
              "- [ ] The docs and the skill explain when to use it and when not to.", ""]
    (folder / "TRACEABILITY.md").write_text("\n".join(lines))
    print(f"Wrote {(folder / 'TRACEABILITY.md').relative_to(ROOT.parent)}")
    if kyverno == "FAIL" or render == "FAIL":
        failed = True
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="check definitions and what was generated from them")
    v.add_argument("names", nargs="*")
    v.add_argument("--definition-only", action="store_true", help="only check the definition (before an agent builds it)")
    t = sub.add_parser("trace", help="write TRACEABILITY.md")
    t.add_argument("name")
    t.add_argument("--junit", type=Path)
    t.add_argument("--kyverno", choices=["PASS", "FAIL"])
    t.add_argument("--render", choices=["PASS", "FAIL"])
    args = parser.parse_args(argv)
    if args.command == "validate":
        return validate(args.names, args.definition_only)
    return trace(args.name, args.junit, args.kyverno, args.render)


if __name__ == "__main__":
    sys.exit(main())
