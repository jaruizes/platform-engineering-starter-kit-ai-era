import importlib.util
import json
from pathlib import Path

GATE = Path(__file__).parents[1].parent.parent / "engineering/quality/gate.py"
SPEC = importlib.util.spec_from_file_location("quality_gate", GATE)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def reports(root: Path, archunit: bool = True, failures: int = 0) -> None:
    profile = root / ".platform/quality/profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({"profile": "backend-spring-v2", "architecture": "backend-spring-v2",
                                   "version": 1, "blocking": ["junit", "archunit", "coverage-report"],
                                   "minimumLineCoveragePercent": 0}))
    sure = root / "target/surefire-reports"
    sure.mkdir(parents=True)
    classname = "sample.ArchitectureTest" if archunit else "sample.OtherTest"
    failure = '<failure message="architecture violation">domain depends on persistence</failure>' if failures else ''
    (sure / "TEST-one.xml").write_text(
        f'<testsuite tests="1" failures="{failures}" errors="0"><testcase classname="{classname}" name="architecture">{failure}</testcase></testsuite>'
    )
    jacoco = root / "target/site/jacoco"
    jacoco.mkdir(parents=True)
    (jacoco / "jacoco.xml").write_text('<report><counter type="LINE" missed="1" covered="9"/></report>')


def test_pass_result_is_deterministic_and_commit_linked(tmp_path):
    reports(tmp_path)
    first = gate.evaluate(tmp_path, "backend-spring-v2", "abc123")
    second = gate.evaluate(tmp_path, "backend-spring-v2", "abc123")
    assert first == second
    assert first["status"] == "passed"
    assert first["sourceCommit"] == "abc123"
    assert first["checks"][2]["lineCoveragePercent"] == 90


def test_archunit_missing_or_failing_junit_blocks_gate(tmp_path):
    reports(tmp_path, archunit=False, failures=1)
    result = gate.evaluate(tmp_path, "backend-spring-v2", "abc123")
    assert result["status"] == "failed"
    assert [check["id"] for check in result["checks"] if check["status"] == "failed"] == ["junit", "archunit"]
    assert result["checks"][0]["failureDetails"][0]["detail"] == "domain depends on persistence"
