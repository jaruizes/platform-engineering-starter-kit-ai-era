"""Code Golden Paths: repositories generated from the platform's skeletons.

Each code Golden Path lives in platform/capabilities/golden-paths/<name>/:
golden-path.yaml says what it needs and how its skeleton is rendered. The
platform runs it the same way for every channel (portal form, platform MCP
server, CLI): no channel renders skeletons or creates repositories itself.

Skeletons use the template syntax people already know from the developer
portal: ${{ values.x }} for values and {% if %} blocks.
"""

from __future__ import annotations

import fnmatch
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml
from jinja2 import StrictUndefined, Undefined
from jinja2.sandbox import SandboxedEnvironment

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "golden-paths"
TEAM = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")
ENVIRONMENT = re.compile(r"^[a-z0-9]([-a-z0-9]{0,28}[a-z0-9])?$")
SERVICE = re.compile(r"^[a-z]([-a-z0-9]{0,38}[a-z0-9])?$")
# Who asked for it: a person (user:default/ana) or an agent (agent:claude-code).
REQUESTER = re.compile(r"^(user:default/[a-z0-9]([-a-z0-9]*[a-z0-9])?|agent:[A-Za-z0-9][-A-Za-z0-9_.]{0,62})$")


class InvalidRequest(ValueError):
    """The request does not meet what the Golden Path needs."""


def golden_paths_dir() -> Path:
    return Path(os.environ.get("GOLDEN_PATHS_DIR", DEFAULT_DIR))


def _environment(undefined: type[Undefined] = Undefined) -> SandboxedEnvironment:
    # The delimiters of the portal's templates. Undefined values render empty,
    # as in the portal, so optional values can be left out.
    return SandboxedEnvironment(
        variable_start_string="${{",
        variable_end_string="}}",
        keep_trailing_newline=True,
        autoescape=False,
        undefined=undefined,
    )


@dataclass
class Parameter:
    name: str
    description: str = ""
    required: bool = False
    default: str | None = None
    pattern: str | None = None
    type: str = "string"
    environment_parameter: str | None = None


@dataclass
class CodeGoldenPath:
    name: str
    title: str
    description: str
    directory: Path
    parameters: list[Parameter]
    values: dict[str, str]
    copy_without_templating: list[str] = field(default_factory=list)
    repository: dict[str, str] = field(default_factory=dict)

    @property
    def skeleton(self) -> Path:
        return self.directory / "skeleton"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "parameters": [
                {k: v for k, v in {
                    "name": p.name,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "pattern": p.pattern,
                    "type": p.type,
                }.items() if v not in (None, "")}
                for p in self.parameters
            ],
        }


def load(directory: Path) -> CodeGoldenPath:
    spec_file = directory / "golden-path.yaml"
    document = yaml.safe_load(spec_file.read_text())
    meta, spec = document["metadata"], document["spec"]
    parameters = [
        Parameter(
            name=name,
            description=(options or {}).get("description", ""),
            required=bool((options or {}).get("required", False)),
            default=(options or {}).get("default"),
            pattern=(options or {}).get("pattern"),
            type=(options or {}).get("type", "string"),
            environment_parameter=(options or {}).get("environmentParameter"),
        )
        for name, options in (spec.get("parameters") or {}).items()
    ]
    skeleton = (directory / spec.get("skeleton", "./skeleton")).resolve()
    if skeleton != (directory / "skeleton").resolve():
        raise ValueError(f"{spec_file}: the skeleton must be ./skeleton")
    return CodeGoldenPath(
        name=meta["name"],
        title=meta.get("title", meta["name"]),
        description=" ".join(str(meta.get("description", "")).split()),
        directory=directory,
        parameters=parameters,
        values={k: str(v) for k, v in (spec.get("values") or {}).items()},
        copy_without_templating=list(spec.get("copyWithoutTemplating") or []),
        repository={k: str(v) for k, v in (spec.get("repository") or {}).items()},
    )


def catalog(directory: Path | None = None) -> dict[str, CodeGoldenPath]:
    """Every code Golden Path of the platform, by name."""
    base = directory or golden_paths_dir()
    found = {}
    for spec_file in sorted(base.glob("*/golden-path.yaml")):
        path = load(spec_file.parent)
        found[path.name] = path
    return found


# --- Requests ----------------------------------------------------------------

# Checks against the platform's current state, provided by the caller so this
# module stays independent of Kubernetes: environment_exists(name) and
# spring_service_exists(name, environment).
@dataclass
class State:
    environment_exists: Callable[[str], bool] = lambda _name: True
    spring_service_exists: Callable[[str, str], bool] = lambda _name, _env: True


def _last_segment(value: str) -> str:
    # The portal's pickers return entity refs such as resource:default/payments-dev.
    return value.split("/")[-1]


def resolve_parameters(path: CodeGoldenPath, given: dict[str, Any], state: State | None = None) -> dict[str, str]:
    """Validates the parameters of a request and fills in the defaults."""
    state = state or State()
    known = {p.name for p in path.parameters}
    unknown = sorted(set(given) - known)
    if unknown:
        raise InvalidRequest(f"Unknown parameters for {path.name}: {', '.join(unknown)}.")
    resolved: dict[str, str] = {}
    for p in path.parameters:
        value = given.get(p.name)
        value = "" if value is None else str(value).strip()
        if not value and p.default is not None:
            value = str(p.default)
        if not value:
            if p.required:
                raise InvalidRequest(f"{p.name} is required: {p.description}")
            resolved[p.name] = ""
            continue
        if p.type == "team":
            team = _last_segment(value)
            if not TEAM.match(team):
                raise InvalidRequest(f"{p.name} must be a team name, for example checkout.")
            value = f"group:default/{team}"
        elif p.type == "environment":
            value = _last_segment(value)
            if not ENVIRONMENT.match(value):
                raise InvalidRequest(f"{p.name} must be an environment name.")
        elif p.type == "spring-service":
            value = _last_segment(value)
            if not SERVICE.match(value):
                raise InvalidRequest(f"{p.name} must be a SpringService name.")
        if p.pattern and not re.match(p.pattern, value):
            raise InvalidRequest(f"{p.name} does not match {p.pattern}.")
        resolved[p.name] = value
    # Checks against what exists, once every value is known.
    for p in path.parameters:
        value = resolved[p.name]
        if not value:
            continue
        if p.type == "environment" and not state.environment_exists(value):
            raise InvalidRequest(f"Environment '{value}' does not exist. Request it first.")
        if p.type == "spring-service":
            environment = resolved.get(p.environment_parameter or "", "")
            if not environment:
                raise InvalidRequest(f"{p.name} needs {p.environment_parameter or 'an environment'}.")
            if not state.spring_service_exists(value, environment):
                raise InvalidRequest(f"SpringService '{value}' not found in env-{environment}. Deploy it first.")
    return resolved


def render_values(path: CodeGoldenPath, parameters: dict[str, str], requester: str) -> dict[str, str]:
    """What the skeleton sees as values.<key>, from golden-path.yaml."""
    if not REQUESTER.match(requester):
        raise InvalidRequest("requester must be user:default/<name> or agent:<name>.")
    env = _environment(StrictUndefined)
    context = {"parameters": parameters, "requester": requester}
    return {key: env.from_string(expression).render(context) for key, expression in path.values.items()}


def render_repository(path: CodeGoldenPath, parameters: dict[str, str]) -> dict[str, str]:
    env = _environment(StrictUndefined)
    return {key: env.from_string(expression).render(parameters=parameters) for key, expression in path.repository.items()}


@dataclass
class RenderedFile:
    path: str
    content: bytes
    executable: bool = False


def render_skeleton(path: CodeGoldenPath, values: dict[str, str]) -> list[RenderedFile]:
    """Renders file names and contents of the skeleton, keeping executable bits."""
    env = _environment()
    files = []
    for source in sorted(p for p in path.skeleton.rglob("*") if p.is_file()):
        relative = source.relative_to(path.skeleton).as_posix()
        target = env.from_string(relative).render(values=values)
        if not target or target.startswith("/") or ".." in Path(target).parts:
            raise ValueError(f"{relative} renders to an unsafe path: {target!r}")
        raw = source.read_bytes()
        verbatim = any(fnmatch.fnmatch(relative, pattern) for pattern in path.copy_without_templating)
        if not verbatim:
            try:
                raw = env.from_string(raw.decode("utf-8")).render(values=values).encode("utf-8")
            except UnicodeDecodeError:
                pass  # Binary files are copied as they are.
        executable = bool(source.stat().st_mode & stat.S_IXUSR)
        files.append(RenderedFile(target, raw, executable))
    return files
