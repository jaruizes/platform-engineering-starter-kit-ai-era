"""Read-only access to commit-linked quality evidence in service repositories."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

SERVICE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$")


def quality_status(service: str) -> dict:
    if not SERVICE.fullmatch(service):
        raise ValueError("service must be a lowercase repository name")
    base = os.getenv("QUALITY_GIT_URL", "http://gitea.platform-system.svc:3000").rstrip("/")
    url = f"{base}/platform/{service}/raw/branch/platform-quality-evidence/.platform/quality/results.json"
    try:
        with urlopen(url, timeout=5) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        if error.code == 404:
            return {"service": service, "status": "unknown", "reason": "No committed quality evidence found."}
        raise RuntimeError(f"Quality evidence request failed with HTTP {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read quality evidence: {error}") from error
    return {
        "service": service,
        "status": result.get("status", "unknown"),
        "sourceCommit": result.get("sourceCommit"),
        "architecture": result.get("architecture"),
        "profile": result.get("profile"),
        "checks": result.get("checks", []),
        "findings": [check for check in result.get("checks", []) if check.get("status") == "failed"],
    }
