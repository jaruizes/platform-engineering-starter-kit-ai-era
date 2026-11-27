"""Capability proposals: a new platform capability starts as a definition.

A platform engineer describes what the platform needs (a CapabilityDefinition,
platform/capabilities/schema/capability-definition.schema.json). The platform
validates it and opens a pull request in the platform repository, where an
agent builds it and a person validates it. Any channel can send it: the
portal's form, the CLI or another tool.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "capability-definition.schema.json"
DEFINITION_PATH = "platform/capabilities/infrastructure/{name}/capability.yaml"


class InvalidDefinition(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("The definition is not valid:\n- " + "\n- ".join(errors))
        self.errors = errors


def schema() -> dict[str, Any]:
    return json.loads(Path(os.environ.get("CAPABILITY_SCHEMA", DEFAULT_SCHEMA)).read_text())


def errors(definition: Any) -> list[str]:
    validator = Draft202012Validator(schema())
    found = sorted(validator.iter_errors(definition), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(str(p) for p in e.absolute_path) or '(root)'} {e.message}" for e in found]


def validate(definition: Any) -> None:
    if problems := errors(definition):
        raise InvalidDefinition(problems)


def file_content(definition: dict[str, Any]) -> str:
    return (
        "# Written by a platform engineer and proposed through the platform.\n"
        "# An agent builds the capability from it (build-platform-capability skill);\n"
        "# a person on the platform team validates the result. Agents never edit it.\n"
        + yaml.safe_dump(definition, sort_keys=False, width=100, allow_unicode=True)
    )


def pull_request_body(definition: dict[str, Any], requested_by: str) -> str:
    meta, spec = definition["metadata"], definition["spec"]
    rules = [*spec["guardrails"].get("everyone", []), *spec["guardrails"].get("agents", [])]
    parameters = spec["interface"].get("parameters", [])
    return "\n".join([
        f"**{meta['title']}** (`{spec['interface']['kind']}`), proposed by {requested_by} through the platform.",
        "",
        f"> {spec['purpose']['problem']}",
        "",
        f"- {len(parameters)} parameters: " + (", ".join(f"`{p['name']}`" for p in parameters) or "none"),
        f"- {len(rules)} guardrails: " + ", ".join(f"{r['id']} ({r['enforcement']})" for r in rules),
        f"- {len(spec['acceptance'])} acceptance criteria: " + ", ".join(a["id"] for a in spec["acceptance"]),
        "",
        "## Next steps",
        "",
        "1. **An agent builds it** on this branch with the `build-platform-capability` skill in "
        "`platform/ai/agent-tooling/skills/`, using Claude Code, Codex or Gemini CLI:",
        '   _"Build the capability in this pull request"_. It never changes `capability.yaml`; '
        "if something is unclear it asks here.",
        "2. **CI checks it** against this definition (`platform/capabilities/tools/check.sh`) and writes `TRACEABILITY.md`.",
        "3. **A person on the platform team validates it** and merges. It becomes available as experimental.",
    ])
