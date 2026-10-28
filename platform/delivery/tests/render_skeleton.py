"""Renders the Spring service template's skeleton the way the portal does,
for tests that run without the portal (see platform/delivery/tests/e2e.sh).

    python3 render_skeleton.py <output dir> name=... description=... owner=...
        module=... environment=... requestedBy=...
"""

import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path

import jinja2

ROOT = Path(__file__).resolve().parents[3]
SKELETON = ROOT / "interfaces/portal/catalog/templates/spring-service/skeleton"
# The template's copyWithoutTemplating.
VERBATIM = [".gitea/workflows/*"]


def values(params: dict[str, str]) -> dict[str, str]:
    """The values block of the template's fetch:template step."""
    base = params.get("basePackage", "com.starterkit")
    name = params["name"]
    return {
        "name": name,
        "description": params.get("description", name),
        "owner": params.get("owner", "group:default/platform-team"),
        "module": params["module"],
        "basePackage": base,
        "rootPackage": f"{base}.{name.replace('-', '')}",
        "packagePath": f"{base}.{name.replace('-', '')}".replace(".", "/"),
        "dbName": name.replace("-", "_"),
        "requestedBy": params.get("requestedBy", "user:default/guest"),
        "environment": (params.get("environment") or "").split("/")[-1],
    }


def main() -> None:
    out = Path(sys.argv[1])
    v = values(dict(arg.split("=", 1) for arg in sys.argv[2:]))
    env = jinja2.Environment(variable_start_string="${{", variable_end_string="}}",
                             keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    for source in SKELETON.rglob("*"):
        if source.is_dir():
            continue
        relative = source.relative_to(SKELETON).as_posix()
        target = out / env.from_string(relative).render(values=v)
        target.parent.mkdir(parents=True, exist_ok=True)
        if any(fnmatch(relative, pattern) for pattern in VERBATIM) or source.name in ("mvnw", "mvnw.cmd"):
            shutil.copy2(source, target)
        else:
            target.write_text(env.from_string(source.read_text()).render(values=v))
            shutil.copymode(source, target)


if __name__ == "__main__":
    main()
