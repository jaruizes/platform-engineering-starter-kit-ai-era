#!/usr/bin/env python3
"""Deterministic quality gate for the architecture profile selected by a service."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def evaluate(root: Path, architecture: str, commit: str | None = None) -> dict:
    profile_path = root / ".platform/quality/profile.json"
    if not profile_path.exists():
        profile_path = root / "engineering/quality/profiles" / f"{architecture}.json"
    profile = json.loads(profile_path.read_text())
    reports = sorted((root / "target/surefire-reports").glob("TEST-*.xml"))
    tests = failures = errors = skipped = 0
    archunit_seen = False
    failure_details: list[dict[str, str]] = []
    for path in reports:
        suite = ET.parse(path).getroot()
        tests += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
        for case in suite.iter("testcase"):
            for outcome in (case.find("failure"), case.find("error")):
                if outcome is not None:
                    failure_details.append({
                        "test": f"{case.attrib.get('classname', '')}.{case.attrib.get('name', '')}".strip("."),
                        "message": outcome.attrib.get("message", outcome.tag),
                        "detail": (outcome.text or "").strip()[:4000],
                    })
            if ("ArchitectureTest" in (case.attrib.get("classname", "") + case.attrib.get("name", ""))
                    and case.find("skipped") is None):
                archunit_seen = True
    failure_details.sort(key=lambda item: (item["test"], item["message"], item["detail"]))

    coverage_path = root / "target/site/jacoco/jacoco.xml"
    covered = missed = 0
    if coverage_path.exists():
        tree = ET.parse(coverage_path)
        for counter in tree.getroot().findall("counter"):
            if counter.attrib.get("type") == "LINE":
                covered = int(counter.attrib["covered"])
                missed = int(counter.attrib["missed"])
                break
    total_lines = covered + missed
    coverage = round(100 * covered / total_lines, 2) if total_lines else 0.0

    checks = [
        {"id": "junit", "status": "passed" if reports and tests > 0 and failures == errors == 0 else "failed",
         "tests": tests, "failures": failures, "errors": errors, "skipped": skipped,
         "failureDetails": failure_details},
        {"id": "archunit", "status": "passed" if archunit_seen and failures == errors == 0 else "failed",
         "evidence": "Surefire test cases include ArchitectureTest" if archunit_seen else "ArchitectureTest result missing"},
        {"id": "coverage-report", "status": "passed" if coverage_path.exists() and coverage >= float(profile["minimumLineCoveragePercent"]) else "failed",
         "lineCoveragePercent": coverage, "coveredLines": covered, "missedLines": missed},
    ]
    result = {
        "schemaVersion": 1,
        "sourceCommit": commit or _commit(root),
        "architecture": profile["architecture"],
        "profile": {"name": profile["profile"], "version": profile["version"]},
        "status": "passed" if all(
            c["id"] not in profile["blocking"] or c["status"] == "passed" for c in checks
        ) else "failed",
        "blockingChecks": profile["blocking"],
        "checks": checks,
    }
    return result


def _commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--architecture", default="backend-spring-v2")
    parser.add_argument("--output", type=Path, default=Path(".platform/quality/results.json"))
    args = parser.parse_args()
    result = evaluate(args.root.resolve(), args.architecture)
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
