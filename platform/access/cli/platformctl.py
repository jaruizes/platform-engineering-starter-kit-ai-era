#!/usr/bin/env python3
"""platformctl: the platform from the terminal, without a portal.

A thin channel of the platform API, like the portal and the platform MCP
server: the same Golden Paths and the same checks, whichever you use.

    platformctl.py golden-paths
    platformctl.py create spring-service name=loyalty-points description="Loyalty points" \\
        owner=checkout module=points environment=checkout-dev
    platformctl.py propose platform/capabilities/infrastructure/redis-cache/capability.yaml

Settings (environment variables):
    PLATFORM_API_URL    default http://localhost:8083 (make up); on AWS, https://<host>:8083
    PLATFORM_API_TOKEN  the channel token (kubectl -n platform-system get secret platform-api-token
                        -o jsonpath='{.data.token}' | base64 -d)
    PLATFORM_USER       who you are, until sign-in with Keycloak: user:default/<name>
                        (default user:default/$USER)
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = os.environ.get("PLATFORM_API_URL", "http://localhost:8083").rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if token := os.environ.get("PLATFORM_API_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read())
        except ValueError:
            detail = {}
        raise SystemExit(f"The platform refused it ({err.code}): {detail.get('error', err.reason)}") from None
    except urllib.error.URLError as err:
        raise SystemExit(f"The platform API is not reachable at {url}: {err.reason}") from None


def requester() -> str:
    return os.environ.get("PLATFORM_USER") or f"user:default/{getpass.getuser().lower()}"


def load_definition(file: Path) -> dict[str, Any]:
    text = file.read_text()
    if file.suffix == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError:
        raise SystemExit("Reading YAML needs PyYAML (pip install pyyaml), or pass the definition as JSON.") from None
    return yaml.safe_load(text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="platformctl", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("golden-paths", help="List the code Golden Paths and their parameters")
    create = commands.add_parser("create", help="Create a repository with a code Golden Path")
    create.add_argument("golden_path")
    create.add_argument("parameters", nargs="*", metavar="key=value")
    propose = commands.add_parser("propose", help="Propose a new platform capability (CapabilityDefinition)")
    propose.add_argument("definition", type=Path)
    propose.add_argument("--name", help="Your name, as it appears in the pull request")
    args = parser.parse_args(argv)

    if args.command == "golden-paths":
        for path in call("GET", "/v1/golden-paths"):
            print(f"{path['name']}: {path['description']}")
            for p in path["parameters"]:
                flag = "required" if p.get("required") else f"default {p['default']}" if "default" in p else "optional"
                print(f"    {p['name']} ({flag}): {p.get('description', '')}")
    elif args.command == "create":
        bad = [p for p in args.parameters if "=" not in p]
        if bad:
            raise SystemExit(f"Parameters are key=value: {', '.join(bad)}")
        parameters = dict(p.split("=", 1) for p in args.parameters)
        result = call("POST", f"/v1/golden-paths/{args.golden_path}/repositories",
                      {"parameters": parameters, "requester": requester()})
        print(json.dumps(result, indent=2))
    elif args.command == "propose":
        result = call("POST", "/v1/capability-proposals", {
            "definition": load_definition(args.definition),
            "requester": requester(),
            "requesterName": args.name or requester(),
        })
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
