"""Transport-free validation and HTTP client, shared by MCP tools and tests.

The YAML/JSON contract is an explicit allowlist, NOT arbitrary HTTP proxying.
Only GET and fixed relative paths are supported. Query parameter values are
validated and URL-encoded; credentials come only from the environment.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
PARAMETER_NAME = re.compile(r"^[a-z][a-zA-Z0-9_]{0,63}$")
PATH = re.compile(r"^/api/[a-zA-Z0-9/_-]+$")
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


class ContractError(ValueError):
    """The adapter configuration or a query violates the published contract."""


def load_contract(file: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(file).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("operations"), list):
        raise ContractError("The contract requires an operations array")
    seen: set[str] = set()
    for op in raw["operations"]:
        if not isinstance(op, dict):
            raise ContractError("Each operation must be an object")
        name, path = op.get("name"), op.get("path")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in seen:
            raise ContractError(f"Invalid or duplicate operation: {name}")
        seen.add(name)
        if op.get("method") != "GET" or not isinstance(path, str) or not PATH.fullmatch(path):
            raise ContractError(f"{name}: only fixed /api/... GET paths are supported")
        params = op.get("parameters", {})
        if not isinstance(params, dict):
            raise ContractError(f"{name}: parameters must be an object")
        for key, schema in params.items():
            if not PARAMETER_NAME.fullmatch(key) or not isinstance(schema, dict) or schema.get("type") not in TYPES:
                raise ContractError(f"{name}: invalid query parameter: {key}")
            if not isinstance(schema.get("required", False), bool):
                raise ContractError(f"{name}: required must be boolean")
    return raw


def validate_parameters(op: dict[str, Any], supplied: dict[str, Any]) -> dict[str, str]:
    declared = op.get("parameters", {})
    if not isinstance(supplied, dict) or set(supplied) - set(declared):
        raise ContractError("Unknown or malformed query parameters")
    result: dict[str, str] = {}
    for key, schema in declared.items():
        if key not in supplied:
            if schema.get("required"):
                raise ContractError(f"Missing required parameter: {key}")
            continue
        value = supplied[key]
        kind = schema["type"]
        # bool is an int subclass and must never accidentally pass integer checks.
        if kind in ("integer", "number") and isinstance(value, bool):
            raise ContractError(f"Invalid value for {key}")
        if not isinstance(value, TYPES[kind]):
            raise ContractError(f"Invalid {kind} value for {key}")
        if kind == "string" and (len(value) > 120 or not value.strip()):
            raise ContractError(f"Invalid string length for {key}")
        result[key] = str(value).lower() if isinstance(value, bool) else str(value)
    return result


def query_api(contract: dict[str, Any], operation: str, parameters: dict[str, Any],
              base_url: str | None = None, token: str | None = None) -> Any:
    op = next((item for item in contract["operations"] if item["name"] == operation), None)
    if op is None:
        raise ContractError(f"Operation '{operation}' is not allowlisted")
    params = validate_parameters(op, parameters)
    base = (base_url or os.environ.get("REST_API_BASE_URL", "http://127.0.0.1:18080")).rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
        raise ContractError("REST_API_BASE_URL must be an http(s) origin, without credentials or query")
    # Local stdio uses a port-forward. Remote HTTP pods can call only the
    # explicitly configured Kubernetes service, not arbitrary plaintext hosts.
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost"):
        trusted = os.getenv("REST_API_TRUSTED_CLUSTER_HOST", "")
        if (
            not os.getenv("KUBERNETES_SERVICE_HOST")
            or not trusted
            or not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", trusted)
            or parsed.hostname != trusted
        ):
            raise ContractError("Non-local REST API endpoints require HTTPS; only the declared in-cluster service is exempt")
    url = base + op["path"] + ("?" + urlencode(params) if params else "")
    secret = token if token is not None else os.environ.get("REST_API_BEARER_TOKEN", "")
    headers = {"Accept": "application/json"}
    if secret:
        headers["Authorization"] = "Bearer " + secret
    try:
        with urlopen(Request(url, headers=headers, method="GET"), timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Backend returned HTTP {response.status}")
            content = response.read(256 * 1024 + 1)
            if len(content) > 256 * 1024:
                raise RuntimeError("Backend response too large")
            return json.loads(content)
    except HTTPError as exc:
        raise RuntimeError(f"Backend returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("Backend unavailable; verify the port-forward and URL") from exc
