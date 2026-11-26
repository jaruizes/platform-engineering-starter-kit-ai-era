"""Read-only access to commit-linked quality evidence in service repositories."""
from __future__ import annotations

import json
import os
import re
import base64
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERVICE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,38}[a-z0-9])?$")


def _sonar_snapshot(service: str) -> dict | None:
    base = os.getenv("SONAR_HOST_URL", "").rstrip("/")
    token = os.getenv("SONAR_TOKEN", "")
    if not base or not token:
        return None
    auth = base64.b64encode(f"{token}:".encode()).decode()

    def get(path: str) -> dict:
        request = Request(f"{base}{path}", headers={"Authorization": f"Basic {auth}"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    try:
        key = urlencode({"project": service, "ps": 1})
        analysis = get(f"/api/project_analyses/search?{key}")
        issues_query = urlencode({"componentKeys": service, "resolved": "false", "ps": 100})
        issues = get(f"/api/issues/search?{issues_query}")
        gate_query = urlencode({"projectKey": service})
        gate = get(f"/api/qualitygates/project_status?{gate_query}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return {"status": "unavailable", "findings": [], "reason": "SonarQube could not be queried."}

    analyses = analysis.get("analyses", [])
    project_status = gate.get("projectStatus", {})
    findings = sorted(
        ({key: issue.get(key) for key in ("key", "rule", "severity", "type", "message", "line")}
         for issue in issues.get("issues", [])),
        key=lambda issue: (issue.get("severity") or "", issue.get("rule") or "", issue.get("key") or ""),
    )
    return {
        "status": project_status.get("status", "unknown").lower(),
        "sourceCommit": analyses[0].get("revision") if analyses else None,
        "findings": findings,
        "totalFindings": issues.get("total", len(findings)),
    }


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
    result = {
        "service": service,
        "status": result.get("status", "unknown"),
        "sourceCommit": result.get("sourceCommit"),
        "architecture": result.get("architecture"),
        "profile": result.get("profile"),
        "checks": result.get("checks", []),
        "findings": [check for check in result.get("checks", []) if check.get("status") == "failed"],
    }
    # The evidence branch is the authoritative commit-linked result. Sonar's
    # API adds its detailed current findings for the same explicit project key.
    sonar = _sonar_snapshot(service)
    if sonar is not None:
        result["sonar"] = sonar
    return result
