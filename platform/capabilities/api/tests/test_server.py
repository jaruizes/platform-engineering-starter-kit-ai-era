from starlette.testclient import TestClient

from platform_api.identity import Authenticator, Unauthenticated, identity_from_claims
from platform_api.server import create_app

SPRING = {"name": "loyalty-points", "description": "Loyalty points", "owner": "checkout", "module": "points"}

TOKENS = {
    "marta": {"azp": "platformctl", "preferred_username": "marta", "groups": ["checkout"], "client_kind": "person"},
    "ana": {"azp": "platformctl", "preferred_username": "ana", "groups": ["/platform-team"], "client_kind": "person"},
    "ana-portal": {"azp": "portal", "preferred_username": "ana", "groups": ["platform-team"],
                   "realm_access": {"roles": ["approver", "developer"]}, "client_kind": "person"},
    "marta-portal": {"azp": "portal", "preferred_username": "marta", "groups": ["checkout"],
                     "realm_access": {"roles": ["developer"]}, "client_kind": "person"},
    "martas-agent": {"azp": "claude-code", "preferred_username": "marta", "groups": ["checkout"],
                     "client_kind": "agent"},
}


class FakeVerifier:
    def claims(self, token):
        if token not in TOKENS:
            raise Unauthenticated("Invalid token")
        return TOKENS[token]


def client(platform):
    return TestClient(create_app(platform, Authenticator(FakeVerifier())))


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_every_request_needs_a_valid_token(platform):
    api = client(platform)
    missing = api.get("/v1/golden-paths")
    assert missing.status_code == 401 and missing.headers["www-authenticate"].startswith("Bearer")
    assert api.get("/v1/golden-paths", headers=bearer("forged")).status_code == 401
    assert api.get("/healthz").status_code == 200


def test_who_am_i(platform):
    me = client(platform).get("/v1/me", headers=bearer("martas-agent")).json()
    assert (me["kind"], me["agent"], me["person"], me["teams"]) == ("agent", "claude-code", "marta", ["checkout"])
    assert me["requester"] == "agent:claude-code"


def test_the_identity_comes_from_the_token_not_the_body(platform):
    api = client(platform)
    created = api.post("/v1/golden-paths/spring-service/repositories", headers=bearer("martas-agent"),
                       json={"parameters": SPRING, "requester": "user:default/ana"})
    assert created.status_code == 201
    assert created.json()["requestedBy"] == "agent:claude-code"
    assert api.post("/v1/golden-paths/spring-service/repositories", headers=bearer("marta"),
                    json={"parameters": SPRING}).status_code == 409
    assert api.post("/v1/golden-paths/spring-service/repositories", headers=bearer("marta"),
                    json={"parameters": {"name": "x"}}).status_code == 422


def test_environments_over_http(platform):
    api = client(platform)
    denied = api.post("/v1/environments", headers=bearer("martas-agent"),
                      json={"team": "payments", "name": "pr-9", "purpose": "x"})
    assert denied.status_code == 403 and "Team scope" in denied.json()["error"]
    ok = api.post("/v1/environments", headers=bearer("martas-agent"),
                  json={"team": "checkout", "name": "pr-9", "purpose": "x"})
    assert ok.status_code == 201 and ok.json()["status"] == "accepted"
    names = {e["name"] for e in api.get("/v1/environments", headers=bearer("marta")).json()}
    assert names == {"checkout-dev", "agent-env"}
    assert api.get("/v1/environments/payments-dev", headers=bearer("marta")).status_code == 403
    assert api.get("/v1/environments/nope", headers=bearer("marta")).status_code == 404
    assert api.delete("/v1/environments/checkout-dev", headers=bearer("martas-agent")).status_code == 403
    assert api.delete("/v1/environments/agent-env", headers=bearer("martas-agent")).json()["status"] == "deleted"


def test_capability_proposals(platform, postgres_definition):
    api = client(platform)
    assert api.post("/v1/capability-proposals", headers=bearer("martas-agent"),
                    json={"definition": postgres_definition}).status_code == 403
    assert api.post("/v1/capability-proposals", headers=bearer("marta"),
                    json={"definition": postgres_definition}).status_code == 403
    bad = api.post("/v1/capability-proposals", headers=bearer("ana"), json={"definition": {"kind": "CapabilityDefinition"}})
    assert bad.status_code == 422 and bad.json()["errors"]
    ok = api.post("/v1/capability-proposals", headers=bearer("ana"),
                  json={"definition": postgres_definition, "requesterName": "Ana"})
    assert ok.status_code == 201 and ok.json()["pullRequestNumber"] == 1


def test_the_portal_sends_the_signed_in_persons_token(platform):
    api = client(platform)
    created = api.post("/v1/golden-paths/spring-service/repositories", headers=bearer("marta-portal"),
                       json={"parameters": SPRING})
    assert created.status_code == 201 and created.json()["requestedBy"] == "user:default/marta"
    # There is no channel token, and stating a person in headers does nothing.
    stated = {**bearer("portal-s3cret"), "X-Platform-Requester": "user:default/ana"}
    assert api.get("/v1/me", headers=stated).status_code == 401


def test_approvals_over_http(platform):
    api = client(platform)
    pending = api.post("/v1/environments", headers=bearer("martas-agent"),
                       json={"team": "checkout", "name": "load-test", "purpose": "x", "size": "large"}).json()
    assert pending["status"] == "pending_approval"
    approval_id = pending["approval_id"]
    listed = api.get("/v1/approvals?status=pending", headers=bearer("marta-portal")).json()
    assert [a["id"] for a in listed] == [approval_id] and listed[0]["can_decide"] is False
    own = api.post(f"/v1/approvals/{approval_id}/decision", headers=bearer("marta-portal"),
                   json={"decision": "approve"})
    assert own.status_code == 403 and "approver role" in own.json()["error"]
    assert api.post(f"/v1/approvals/{approval_id}/decision", headers=bearer("martas-agent"),
                    json={"decision": "approve"}).status_code == 403
    assert api.post(f"/v1/approvals/{approval_id}/decision", headers=bearer("ana-portal"),
                    json={"decision": "maybe"}).status_code == 422
    approved = api.post(f"/v1/approvals/{approval_id}/decision", headers=bearer("ana-portal"),
                        json={"decision": "approve", "note": "load test of the week"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert api.post(f"/v1/approvals/{approval_id}/decision", headers=bearer("ana-portal"),
                    json={"decision": "reject"}).status_code == 409
    overview = api.get("/v1/overview", headers=bearer("marta-portal")).json()
    assert {e["name"] for e in overview["environments"]} == {"checkout-dev", "agent-env"}
    assert overview["scope"] == "checkout"


def test_identity_from_keycloak_claims():
    person = identity_from_claims(TOKENS["marta"])
    assert (person.kind, person.person, person.is_agent) == ("person", "marta", False)
    agent = identity_from_claims({**TOKENS["martas-agent"], "client_kind": None})
    assert agent.kind == "agent", "an unknown client is treated as an agent"
    robot = identity_from_claims({"azp": "ci-agent", "preferred_username": "service-account-ci-agent",
                                  "groups": ["payments"], "owner_team": "checkout"})
    assert (robot.kind, robot.agent, robot.teams) == ("autonomous", "ci-agent", ("checkout",))
    chained = identity_from_claims({**TOKENS["martas-agent"], "azp": "test-runner",
                                    "act": {"client_id": "coordinator", "act": {"client_id": "agent-platform"}}})
    assert chained.annotations()["platform.starterkit.dev/agent-chain"] == "coordinator > agent-platform"
