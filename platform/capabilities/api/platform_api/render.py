"""Renders a code Golden Path into a local folder, with the platform's engine
and without creating a repository. For local checks and demos that run
without a cluster (for example make demo-quality).

    python3 -m platform_api.render spring-service <output dir> name=... module=... [key=value ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import golden_paths


def render(golden_path: str, output: Path, parameters: dict[str, str], requester: str = "user:default/ana") -> None:
    path = golden_paths.catalog()[golden_path]
    resolved = golden_paths.resolve_parameters(path, parameters)
    values = golden_paths.render_values(path, resolved, requester)
    for f in golden_paths.render_skeleton(path, values):
        target = output / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.content)
        if f.executable:
            target.chmod(0o755)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    golden_path, output, *pairs = argv
    parameters = dict(pair.split("=", 1) for pair in pairs)
    parameters.setdefault("description", parameters.get("name", golden_path))
    parameters.setdefault("owner", "platform-team")
    render(golden_path, Path(output), parameters)


if __name__ == "__main__":
    main(sys.argv[1:])
