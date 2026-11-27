#!/usr/bin/env python3
"""platformctl: the platform from the terminal, without a portal.

A thin channel of the platform API, like the portal and the platform MCP
server: the same Golden Paths, the same checks and the same identity,
whichever you use. You sign in once with the platform's identity provider
(Keycloak); the platform API knows who you are and which teams you are in.

    platformctl.py login                     # opens a sign-in page, once
    platformctl.py whoami
    platformctl.py environments
    platformctl.py request-environment checkout pr-123 "Test PR 123" --size small --ttl 8
    platformctl.py delete-environment pr-123
    platformctl.py golden-paths
    platformctl.py create spring-service name=loyalty-points description="Loyalty points" \\
        owner=checkout module=points environment=checkout-dev
    platformctl.py propose platform/capabilities/infrastructure/redis-cache/capability.yaml

For an agent with no OAuth sign-in of its own (Codex), a token for that
agent, on behalf of the person who signs in:

    platformctl.py login --client codex
    export PLATFORM_TOKEN="$(platformctl.py token --client codex)"

Settings (environment variables):
    PLATFORM_API_URL    default http://localhost:8083 (make up); on AWS, https://<host>:8083
    PLATFORM_ISSUER     default http://localhost:8180/realms/platform; on AWS, https://<host>:8180/realms/platform
    PLATFORM_TOKEN      an access token to use instead of the one from login (automation)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLIENTS = ("platformctl", "codex")


def issuer() -> str:
    return os.environ.get("PLATFORM_ISSUER", "http://localhost:8180/realms/platform").rstrip("/")


def _token_file(client: str) -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "platformctl"
    return base / f"{client}.json"


def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read()) | {"_status": err.code}
        except ValueError:
            raise SystemExit(f"The identity provider answered {err.code}.") from None
    except urllib.error.URLError as err:
        raise SystemExit(f"The identity provider is not reachable at {url}: {err.reason}") from None


def _save(client: str, tokens: dict[str, Any]) -> None:
    file = _token_file(client)
    file.parent.mkdir(parents=True, exist_ok=True)
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 300))
    file.touch(mode=0o600, exist_ok=True)
    file.write_text(json.dumps(tokens))


def login(client: str) -> None:
    """OAuth device authorization grant: sign in in a browser, from any terminal."""
    endpoint = f"{issuer()}/protocol/openid-connect"
    device = _post_form(f"{endpoint}/auth/device", {"client_id": client, "scope": "openid profile"})
    if "device_code" not in device:
        raise SystemExit(f"Could not start the sign-in: {device.get('error_description') or device}")
    print(f"Open {device.get('verification_uri_complete') or device['verification_uri']} and sign in"
          + ("" if device.get("verification_uri_complete") else f" with the code {device['user_code']}") + ".")
    interval = int(device.get("interval", 5))
    deadline = time.time() + int(device.get("expires_in", 600))
    while time.time() < deadline:
        time.sleep(interval)
        tokens = _post_form(f"{endpoint}/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device["device_code"], "client_id": client,
        })
        error = tokens.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error:
            raise SystemExit(f"Sign-in failed: {tokens.get('error_description') or error}")
        _save(client, tokens)
        print("Signed in.")
        return
    raise SystemExit("The sign-in expired. Run login again.")


def access_token(client: str = "platformctl") -> str:
    """The access token: PLATFORM_TOKEN, or the one from login, refreshed when it expires."""
    if token := os.environ.get("PLATFORM_TOKEN"):
        return token
    file = _token_file(client)
    if not file.exists():
        raise SystemExit(f"Not signed in: run platformctl.py login{'' if client == 'platformctl' else ' --client ' + client}.")
    tokens = json.loads(file.read_text())
    if tokens.get("expires_at", 0) - 30 > time.time():
        return tokens["access_token"]
    refreshed = _post_form(f"{issuer()}/protocol/openid-connect/token", {
        "grant_type": "refresh_token", "refresh_token": tokens.get("refresh_token", ""), "client_id": client,
    })
    if "access_token" not in refreshed:
        raise SystemExit("Your session expired: run platformctl.py login again.")
    _save(client, refreshed)
    return refreshed["access_token"]


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = os.environ.get("PLATFORM_API_URL", "http://localhost:8083").rstrip("/") + path
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token()}"}
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


def load_definition(file: Path) -> dict[str, Any]:
    text = file.read_text()
    if file.suffix == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError:
        raise SystemExit("Reading YAML needs PyYAML (pip install pyyaml), or pass the definition as JSON.") from None
    return yaml.safe_load(text)


def show(result: Any) -> None:
    print(json.dumps(result, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="platformctl", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("login", "Sign in with the platform's identity provider"),
                       ("logout", "Forget the tokens of login"),
                       ("token", "Print an access token (for agents without OAuth sign-in)")):
        command = commands.add_parser(name, help=text)
        command.add_argument("--client", choices=CLIENTS, default="platformctl")
    commands.add_parser("whoami", help="Who the platform sees: you and your teams")
    environments = commands.add_parser("environments", help="List the environments of your teams")
    environments.add_argument("--team")
    request_env = commands.add_parser("request-environment", help="Request an ephemeral environment")
    request_env.add_argument("team")
    request_env.add_argument("name")
    request_env.add_argument("purpose")
    request_env.add_argument("--size", default="small", choices=("small", "medium", "large"))
    request_env.add_argument("--ttl", type=int, default=8, help="hours (max 72)")
    delete_env = commands.add_parser("delete-environment", help="Delete an environment of your teams")
    delete_env.add_argument("name")
    commands.add_parser("golden-paths", help="List the code Golden Paths and their parameters")
    create = commands.add_parser("create", help="Create a repository with a code Golden Path")
    create.add_argument("golden_path")
    create.add_argument("parameters", nargs="*", metavar="key=value")
    propose = commands.add_parser("propose", help="Propose a new platform capability (CapabilityDefinition)")
    propose.add_argument("definition", type=Path)
    propose.add_argument("--name", help="Your name, as it appears in the pull request")
    args = parser.parse_args(argv)

    if args.command == "login":
        login(args.client)
    elif args.command == "logout":
        _token_file(args.client).unlink(missing_ok=True)
        print("Signed out.")
    elif args.command == "token":
        print(access_token(args.client))
    elif args.command == "whoami":
        show(call("GET", "/v1/me"))
    elif args.command == "environments":
        path = "/v1/environments" + (f"?team={urllib.parse.quote(args.team)}" if args.team else "")
        for env in call("GET", path):
            print(f"{env['name']:24} {env['team']:16} {env['size']:7} ready={env['ready']} "
                  f"requested-by={env.get('requested_by')} expires={env['expires_at']}")
    elif args.command == "request-environment":
        show(call("POST", "/v1/environments", {"team": args.team, "name": args.name, "purpose": args.purpose,
                                               "size": args.size, "ttlHours": args.ttl}))
    elif args.command == "delete-environment":
        show(call("DELETE", f"/v1/environments/{urllib.parse.quote(args.name)}"))
    elif args.command == "golden-paths":
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
        show(call("POST", f"/v1/golden-paths/{args.golden_path}/repositories", {"parameters": parameters}))
    elif args.command == "propose":
        show(call("POST", "/v1/capability-proposals", {
            "definition": load_definition(args.definition),
            **({"requesterName": args.name} if args.name else {}),
        }))


if __name__ == "__main__":
    main(sys.argv[1:])
