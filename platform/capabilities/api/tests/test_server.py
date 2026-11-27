from starlette.testclient import TestClient

from platform_api.server import create_app

SPRING = {"name": "loyalty-points", "description": "Loyalty points", "owner": "checkout", "module": "points"}


def client(platform, token="s3cret"):
    return TestClient(create_app(platform, token))


def test_channels_need_the_token(platform):
    api = client(platform)
    assert api.get("/v1/golden-paths").status_code == 401
    assert api.get("/v1/golden-paths", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert api.get("/healthz").status_code == 200


def test_lists_and_runs_code_golden_paths(platform):
    api = client(platform)
    auth = {"Authorization": "Bearer s3cret"}
    names = [p["name"] for p in api.get("/v1/golden-paths", headers=auth).json()]
    assert sorted(names) == ["angular-app", "api-mcp-adapter", "spring-service"]
    created = api.post("/v1/golden-paths/spring-service/repositories", headers=auth,
                       json={"parameters": SPRING, "requester": "user:default/ana"})
    assert created.status_code == 201
    assert created.json()["repository"].endswith("/platform/loyalty-points")
    again = api.post("/v1/golden-paths/spring-service/repositories", headers=auth,
                     json={"parameters": SPRING, "requester": "user:default/ana"})
    assert again.status_code == 409
    invalid = api.post("/v1/golden-paths/spring-service/repositories", headers=auth,
                       json={"parameters": {"name": "x"}, "requester": "user:default/ana"})
    assert invalid.status_code == 422


def test_capability_proposals(platform, postgres_definition):
    api = client(platform)
    auth = {"Authorization": "Bearer s3cret"}
    by_agent = api.post("/v1/capability-proposals", headers=auth,
                        json={"definition": postgres_definition, "requester": "agent:claude-code"})
    assert by_agent.status_code == 403
    bad = api.post("/v1/capability-proposals", headers=auth,
                   json={"definition": {"kind": "CapabilityDefinition"}, "requester": "user:default/ana"})
    assert bad.status_code == 422 and bad.json()["errors"]
    ok = api.post("/v1/capability-proposals", headers=auth,
                  json={"definition": postgres_definition, "requester": "user:default/ana", "requesterName": "Ana"})
    assert ok.status_code == 201
    assert ok.json()["pullRequestNumber"] == 1
