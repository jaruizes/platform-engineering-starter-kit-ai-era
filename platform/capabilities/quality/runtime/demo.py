#!/usr/bin/env python3
"""Run a real ArchUnit failure, remove the violation, and run the passing gate."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "platform/delivery/tests/render_skeleton.py"


def run(command: list[str], cwd: Path, expect_pass: bool, expect_text: str | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if (completed.returncode == 0) != expect_pass or (expect_text and expect_text not in completed.stdout):
        print(completed.stdout)
        raise SystemExit("Quality demo produced an unexpected result.")
    print(completed.stdout[-5000:])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="quality-demo-") as temp:
        service = Path(temp) / "quality-demo"
        subprocess.run([sys.executable, str(RENDER), str(service), "name=quality-demo", "module=demo"], check=True)
        violation = service / "src/main/java/com/starterkit/qualitydemo/demo/domain/InvalidDomain.java"
        violation.parent.mkdir(parents=True, exist_ok=True)
        violation.write_text("""package com.starterkit.qualitydemo.demo.domain;
import jakarta.persistence.Entity;
@Entity public class InvalidDomain {}
""")
        print("1/2: an architectural violation must fail ArchUnit and the quality gate")
        run(["./mvnw", "-B", "-ntp", "verify", "-DskipITs"], service, expect_pass=False,
            expect_text="Architecture Violation")
        violation.unlink()
        print("2/2: after removing the violation, tests and the quality gate must pass")
        run(["./mvnw", "-B", "-ntp", "verify", "-DskipITs"], service, expect_pass=True)
        run([sys.executable, ".platform/quality/gate.py", "--architecture", "backend-spring-v2"], service, expect_pass=True)


if __name__ == "__main__":
    main()
