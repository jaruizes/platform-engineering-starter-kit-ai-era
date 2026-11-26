"""Regression checks for the Golden Paths copied into new service repos."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ANGULAR = ROOT / "platform/capabilities/golden-paths/angular-app/skeleton"
MCP = ROOT / "platform/capabilities/golden-paths/api-mcp-adapter/skeleton"


def test_angular20_builder_coverage_options_and_sonar_configuration():
    workspace = json.loads((ANGULAR / "angular.json").read_text())
    project = workspace["projects"]["${{ values.name }}"]
    opts = project["architect"]["test"]["options"]
    assert opts["codeCoverage"] is True
    assert "lcov" in opts["codeCoverageReporters"]
    assert "coverage" not in opts and "coverageReporters" not in opts
    scripts = json.loads((ANGULAR / "package.json").read_text())["scripts"]
    assert "--coverage" not in scripts["test"]
    assert "normalize-lcov.mjs" in scripts["test"]
    sonar = (ANGULAR / "sonar-project.properties").read_text()
    assert "sonar.test.inclusions=**/*.spec.ts" in sonar
    assert "sonar.exclusions=**/*.spec.ts" in sonar
    assert "coverage/lcov.info" in sonar


def test_crane_multiarch_workflow_and_fail_closed_image_publication():
    wf = (ANGULAR / ".gitea/workflows/deliver.yaml").read_text()
    assert "--new_layer" in wf and "--new_tag" in wf
    assert "for ARCH in amd64 arm64" in wf
    assert "crane index append" in wf
    assert 'crane manifest "$IMAGE"' in wf
    assert "--file /tmp/angular-image.tar --tag" not in wf


def test_mcp_adapter_uses_explicit_tool_errors():
    server = (MCP / "rest_mcp_adapter/server.py").read_text()
    bridge = (MCP / "rest_mcp_adapter/bridge.py").read_text()
    assert "mcp.server.mcpserver.exceptions import ToolError" in server
    assert "raise ToolError(str(exc))" in server
    assert "PARAMETER_NAME" in bridge
