#!/usr/bin/env python3
"""Enforce basic Angular feature/import boundaries without relying on AI review."""
import json
import re
from pathlib import Path

root = Path("src/app")
findings = []
import_pattern = re.compile(r"(?:from\s+|import\s*\()(['\"])([^'\"]+)\1")
for path in sorted(root.rglob("*.ts")):
    rel = path.relative_to(root).as_posix()
    current_feature = re.match(r"features/([^/]+)/", rel)
    for _, target in import_pattern.findall(path.read_text()):
        normalized = target.replace("\\", "/")
        resolved = (path.parent / target).resolve() if target.startswith(".") else None
        target_rel = resolved.relative_to(Path.cwd().resolve() / root) if resolved and resolved.is_relative_to((Path.cwd() / root).resolve()) else Path(normalized)
        target_text = target_rel.as_posix()
        target_feature = re.match(r"features/([^/]+)/", target_text)
        if current_feature and target_feature and current_feature.group(1) != target_feature.group(1):
            findings.append({"file": rel, "rule": "FA-002", "import": target, "message": "Feature code must not import another feature."})
        if rel.startswith("shared/") and target_feature:
            findings.append({"file": rel, "rule": "FA-002", "import": target, "message": "Shared code must not import feature code."})
        if ("@angular/common/http" in target or target_text.startswith("api/")) and not (
            rel.startswith("core/") or re.match(r"features/[^/]+/data-access/", rel) or rel.startswith("api/")
        ):
            findings.append({"file": rel, "rule": "FA-003", "import": target, "message": "HTTP and generated API imports belong in core or feature data-access."})
    if "@NgModule" in path.read_text():
        findings.append({"file": rel, "rule": "FA-006", "message": "NgModule declarations are not allowed."})
out = Path(".platform/quality/architecture-findings.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n")
print(json.dumps(findings, indent=2))
raise SystemExit(bool(findings))
