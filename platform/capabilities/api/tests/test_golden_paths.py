"""Code Golden Paths are platform capabilities: the platform renders them,
whatever the channel, from golden-path.yaml and the skeleton."""

import pytest
import yaml

from platform_api import golden_paths
from platform_api.golden_paths import InvalidRequest

from .conftest import ROOT

SPRING = {"name": "loyalty-points", "description": "Loyalty points", "owner": "checkout", "module": "points"}


def files_of(path, values):
    return {f.path: f for f in golden_paths.render_skeleton(path, values)}


def test_every_code_golden_path_is_a_platform_capability(catalog):
    assert set(catalog) == {"spring-service", "angular-app", "api-mcp-adapter"}


@pytest.mark.parametrize("name", ["spring-service", "angular-app", "api-mcp-adapter"])
def test_the_portal_form_only_asks_for_what_the_golden_path_takes(catalog, name):
    template = yaml.safe_load((ROOT / f"platform/capabilities/golden-paths/{name}/template.yaml").read_text())
    form = {key for page in template["spec"]["parameters"] for key in page.get("properties", {})}
    assert form <= {p.name for p in catalog[name].parameters}
    steps = template["spec"]["steps"]
    # The portal no longer renders skeletons or creates repositories itself.
    assert [s["action"] for s in steps] == ["platform:golden-path:create"]
    assert steps[0]["input"]["goldenPath"] == name


def test_parameters_are_validated_and_normalized(catalog):
    path = catalog["spring-service"]
    resolved = golden_paths.resolve_parameters(
        path, {**SPRING, "owner": "group:default/checkout", "environment": "resource:default/checkout-dev"})
    assert resolved["owner"] == "group:default/checkout"
    assert resolved["environment"] == "checkout-dev"
    assert resolved["basePackage"] == "com.starterkit"
    with pytest.raises(InvalidRequest, match="module is required"):
        golden_paths.resolve_parameters(path, {k: v for k, v in SPRING.items() if k != "module"})
    with pytest.raises(InvalidRequest, match="name does not match"):
        golden_paths.resolve_parameters(path, {**SPRING, "name": "Loyalty_Points"})
    with pytest.raises(InvalidRequest, match="Unknown parameters"):
        golden_paths.resolve_parameters(path, {**SPRING, "image": "x"})


def test_checks_what_exists_in_the_platform(catalog):
    state = golden_paths.State(lambda e: e == "checkout-dev", lambda s, e: (s, e) == ("orders-service", "checkout-dev"))
    with pytest.raises(InvalidRequest, match="Environment 'nope' does not exist"):
        golden_paths.resolve_parameters(catalog["spring-service"], {**SPRING, "environment": "nope"}, state)
    adapter = {"name": "orders-mcp", "description": "Orders tools", "owner": "checkout",
               "backendService": "payments-service", "environment": "checkout-dev"}
    with pytest.raises(InvalidRequest, match="SpringService 'payments-service' not found"):
        golden_paths.resolve_parameters(catalog["api-mcp-adapter"], adapter, state)
    adapter["backendService"] = "orders-service"
    assert golden_paths.resolve_parameters(catalog["api-mcp-adapter"], adapter, state)["backendService"] == "orders-service"


def test_requester_is_a_person_or_an_agent(catalog):
    path = catalog["spring-service"]
    resolved = golden_paths.resolve_parameters(path, SPRING)
    assert golden_paths.render_values(path, resolved, "agent:claude-code")["requestedBy"] == "agent:claude-code"
    assert golden_paths.render_values(path, resolved, "user:default/ana")["requestedBy"] == "user:default/ana"
    with pytest.raises(InvalidRequest):
        golden_paths.render_values(path, resolved, "")


def test_renders_the_spring_service_like_the_portal_did(catalog):
    path = catalog["spring-service"]
    resolved = golden_paths.resolve_parameters(path, {**SPRING, "environment": "checkout-dev"})
    values = golden_paths.render_values(path, resolved, "agent:claude-code")
    assert values["rootPackage"] == "com.starterkit.loyaltypoints"
    assert values["packagePath"] == "com/starterkit/loyaltypoints"
    assert values["dbName"] == "loyalty_points"
    files = files_of(path, values)
    assert "src/main/java/com/starterkit/loyaltypoints/Application.java" in files
    assert "src/main/java/com/starterkit/loyaltypoints/points/business/package-info.java" in files
    assert files["mvnw"].executable
    for f in files.values():
        if not f.path.startswith(".gitea/"):
            assert b"${{ values" not in f.content, f.path
    # The pipeline keeps its own expressions.
    assert b"${{ vars.SERVICE_IMAGE_REPOSITORY }}" in files[".gitea/workflows/deliver.yaml"].content
    catalog_info = yaml.safe_load(files["catalog-info.yaml"].content)
    assert catalog_info["metadata"]["name"] == "loyalty-points"
    assert catalog_info["spec"]["owner"] == "group:default/checkout"
    assert catalog_info["metadata"]["annotations"]["platform.starterkit.dev/requested-by"] == "agent:claude-code"
    service = yaml.safe_load(files["deploy/spring-service.yaml"].content)
    assert service["metadata"]["namespace"] == "env-checkout-dev"
    assert service["metadata"]["annotations"]["platform.starterkit.dev/service-created-by"] == "agent:claude-code"


def test_without_environment_nothing_is_deployed(catalog):
    path = catalog["spring-service"]
    values = golden_paths.render_values(path, golden_paths.resolve_parameters(path, SPRING), "user:default/ana")
    files = files_of(path, values)
    assert "kind: SpringService" not in files["deploy/spring-service.yaml"].content.decode()


def test_renders_the_angular_app_and_the_adapter(catalog):
    angular = catalog["angular-app"]
    resolved = golden_paths.resolve_parameters(angular, {
        "name": "loyalty-web", "description": "Loyalty", "owner": "checkout",
        "environment": "checkout-dev", "backendService": "orders-service"})
    files = files_of(angular, golden_paths.render_values(angular, resolved, "agent:claude-code"))
    app = yaml.safe_load(files["deploy/app.yaml"].content)
    assert app["spec"]["backendService"] == "orders-service"
    assert yaml.safe_load(files["catalog-info.yaml"].content)["spec"]["dependsOn"]

    adapter = catalog["api-mcp-adapter"]
    resolved = golden_paths.resolve_parameters(adapter, {
        "name": "orders-mcp", "description": "Orders tools", "owner": "checkout",
        "backendService": "orders-service", "environment": "checkout-dev"})
    files = files_of(adapter, golden_paths.render_values(adapter, resolved, "agent:claude-code"))
    assert files["scripts/build-image.sh"].executable
    for f in files.values():
        if not f.path.startswith(".gitea/"):
            assert b"${{ values" not in f.content, f.path
