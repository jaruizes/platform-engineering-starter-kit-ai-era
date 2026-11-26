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


def test_remote_mcp_template_deploys_private_kubernetes_service():
    deploy = (MCP / "deploy/mcp.yaml").read_text()
    assert "kind: Deployment" in deploy
    assert "kind: Service" in deploy
    assert "type: ClusterIP" in deploy
    assert "namespace: env-${{ values.environment }}" in deploy
    assert "REST_API_BASE_URL" in deploy and "REST_API_TRUSTED_CLUSTER_HOST" in deploy
    assert "value: streamable-http" in deploy
    assert "automountServiceAccountToken: false" in deploy
    assert "allowPrivilegeEscalation: false" in deploy
    assert not any(token in deploy.lower() for token in ("kind: ingress", "type: loadbalancer"))
    workflow = (MCP / ".gitea/workflows/deliver.yaml").read_text()
    assert "scripts/build-image.sh" in workflow
    assert "deploy/mcp.yaml" in workflow
    assert "pytest" in workflow
    script = (MCP / "scripts/build-image.sh").read_text()
    assert "for ARCH in amd64 arm64" in script
    assert "--only-binary=:all:" in script
    assert "crane index append" in script
    assert "--new_layer" in script and "--new_tag" in script


def test_remote_mcp_template_keeps_scaffolder_workflow_expressions_untouched():
    template = (ROOT / "platform/capabilities/golden-paths/api-mcp-adapter/template.yaml").read_text()
    assert "copyWithoutTemplating:" in template
    assert ".gitea/workflows/*" in template
    assert "required: [environment]" in template
    project = (ROOT / "platform/capabilities/delivery/argocd/services.yaml").read_text()
    assert "kind: Deployment" in project
    assert "kind: Service" in project


def test_remote_mcp_supports_cluster_http_only_for_known_backend():
    source = (MCP / "rest_mcp_adapter/bridge.py").read_text()
    runtime = (MCP / "rest_mcp_adapter/server.py").read_text()
    assert "REST_API_TRUSTED_CLUSTER_HOST" in source
    assert "KUBERNETES_SERVICE_HOST" in source
    assert '"transport": "streamable-http"' in runtime
    assert '"stateless_http": True' in runtime
    assert '"streamable_http_path": "/mcp"' in runtime


def test_angular_csp_nonce_is_per_response_and_used_by_root_element():
    runtime = (ROOT / "platform/capabilities/golden-paths/angular-app/runtime/composition.yaml").read_text()
    root = (ANGULAR / "src/index.html").read_text()
    workspace = json.loads((ANGULAR / "angular.json").read_text())
    assert "style-src 'self' 'nonce-$request_id'" in runtime
    assert "sub_filter '__CSP_NONCE__' $request_id;" in runtime
    assert 'Cache-Control "no-store"' in runtime
    assert 'ngCspNonce="__CSP_NONCE__"' in root
    assert workspace["projects"]["${{ values.name }}"]["architect"]["build"]["configurations"]["production"]["optimization"]["styles"]["inlineCritical"] is False
    assert "unsafe-inline" not in runtime
