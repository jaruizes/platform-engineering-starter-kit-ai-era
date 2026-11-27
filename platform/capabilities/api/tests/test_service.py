import copy

import pytest

from platform_api import proposals
from platform_api.git_server import RepositoryExists
from platform_api.golden_paths import InvalidRequest
from platform_api.service import Forbidden, NotFound

from .conftest import ANA, CARLOS, CI_AGENT, LUIS, LUIS_AGENT, MARTA, MARTA_APPROVER, MARTAS_AGENT

SPRING = {"name": "loyalty-points", "description": "Loyalty points", "owner": "checkout", "module": "points",
          "environment": "checkout-dev"}
ANNOTATION = "platform.starterkit.dev/"


# --- Code Golden Paths ---------------------------------------------------------------------

def test_creates_the_repository_and_records_who_asked(platform):
    result = platform.create_repository(MARTAS_AGENT, "spring-service", SPRING)
    assert result["repository"] == "http://localhost:3000/platform/loyalty-points"
    assert (result["requestedBy"], result["onBehalfOf"]) == ("agent:claude-code", "marta")
    description, files, message = platform.git.repositories["loyalty-points"]
    assert description == "Loyalty points"
    assert "Requested-by: agent:claude-code\nOn-behalf-of: user:default/marta" in message
    assert any(f.path == "catalog-info.yaml" for f in files)
    event = platform.record.events[-1]
    assert (event["action"], event["actor"], event["on_behalf_of"]) == ("RequestAccepted", "agent:claude-code", "marta")
    assert "claude-code for marta created loyalty-points for team checkout" in event["message"]


def test_the_same_request_from_any_channel_gives_the_same_repository(platform):
    by_agent = platform.create_repository(MARTAS_AGENT, "spring-service", SPRING)
    by_person = platform.create_repository(MARTA, "spring-service", {**SPRING, "name": "loyalty-points-2"})
    agent_files = {f.path for f in platform.git.repositories[by_agent["name"]][1]}
    person_files = {f.path.replace("loyaltypoints2", "loyaltypoints") for f in platform.git.repositories[by_person["name"]][1]}
    assert agent_files == person_files


def test_repositories_only_for_your_teams(platform):
    with pytest.raises(Forbidden, match="not payments"):
        platform.create_repository(MARTAS_AGENT, "spring-service", {**SPRING, "owner": "payments"})
    # Nor delivered into another team's environment.
    with pytest.raises(Forbidden, match="deliver into environment payments-dev"):
        platform.create_repository(MARTA, "spring-service", {**SPRING, "environment": "payments-dev"})
    assert platform.git.repositories == {}
    assert platform.record.events[-1]["action"] == "RequestDenied"


def test_rejects_unknown_golden_paths_and_existing_repositories(platform):
    with pytest.raises(InvalidRequest, match="no code Golden Path 'cobol'"):
        platform.create_repository(MARTA, "cobol", {})
    platform.create_repository(MARTA, "spring-service", SPRING)
    with pytest.raises(RepositoryExists):
        platform.create_repository(MARTA, "spring-service", SPRING)
    assert platform.record.events[-1]["action"] == "RequestFailed"


# --- Capability proposals -----------------------------------------------------------------

def test_platform_team_proposes_capabilities(platform, postgres_definition):
    definition = copy.deepcopy(postgres_definition)
    definition["metadata"]["name"] = "redis-cache"
    result = platform.propose_capability(ANA, definition, "Ana")
    proposal = platform.git.proposals[0]
    assert proposal["repository"] == "platform-starter-kit"
    assert proposal["path"] == "platform/capabilities/infrastructure/redis-cache/capability.yaml"
    assert "proposed by Ana through the platform" in proposal["body"]
    assert result["entityRef"] == "resource:default/redis-cache.pr-1"
    assert platform.record.events[-1]["action"] == "CapabilityProposed"


@pytest.mark.parametrize("who", [MARTAS_AGENT, CI_AGENT, MARTA])
def test_agents_and_other_teams_do_not_propose(platform, postgres_definition, who):
    with pytest.raises(Forbidden):
        platform.propose_capability(who, postgres_definition)
    assert platform.git.proposals == []
    assert platform.record.events[-1]["action"] == "RequestDenied"


def test_invalid_definitions_are_not_proposed(platform, postgres_definition):
    definition = copy.deepcopy(postgres_definition)
    del definition["spec"]["acceptance"]
    with pytest.raises(proposals.InvalidDefinition, match="acceptance"):
        platform.propose_capability(ANA, definition)
    assert platform.git.proposals == []


def test_the_pull_request_summarizes_the_definition(postgres_definition):
    body = proposals.pull_request_body(postgres_definition, "Ana")
    assert "**PostgreSQL database** (`PostgresDatabase`), proposed by Ana through the platform" in body
    assert "GR-3 (approval)" in body
    assert "AC-1, AC-2, AC-3, AC-4, AC-5, AC-6" in body


def test_explains_what_is_wrong_with_a_definition(postgres_definition):
    assert proposals.errors(postgres_definition) == []
    bad = copy.deepcopy(postgres_definition)
    del bad["spec"]["acceptance"]
    bad["spec"]["guardrails"]["agents"][0]["enforcement"] = "maybe"
    found = proposals.errors(bad)
    assert "/spec 'acceptance' is a required property" in found
    assert any(e.startswith("/spec/guardrails/agents/0/enforcement") for e in found)


# --- Environments: use cases 1-5 and 13 of docs/identity-and-access.md ----------------------

def test_a_person_gets_an_environment_for_her_team(platform):
    result = platform.request_environment(MARTA, "checkout", "pr-1", "Test PR 1", "medium", 48)
    assert result["status"] == "accepted"
    manifest, as_agent = platform.cluster.created[-1]
    assert as_agent is False
    annotations = manifest["metadata"]["annotations"]
    assert annotations[ANNOTATION + "on-behalf-of"] == "marta"
    assert annotations[ANNOTATION + "requester-teams"] == "checkout"
    assert ANNOTATION + "agent" not in annotations


def test_nobody_requests_for_another_team(platform):
    for who in (MARTA, MARTAS_AGENT):
        with pytest.raises(Forbidden, match="not payments"):
            platform.request_environment(who, "payments", "pr-2", "x")
    assert platform.cluster.created == []
    denied = platform.record.events[-1]
    assert (denied["action"], denied["actor"], denied["on_behalf_of"]) == ("RequestDenied", "agent:claude-code", "marta")


def test_an_agent_acts_as_the_agents_identity_with_its_person(platform):
    assert platform.request_environment(MARTAS_AGENT, "checkout", "pr-3", "x")["status"] == "accepted"
    manifest, as_agent = platform.cluster.created[-1]
    assert as_agent is True
    annotations = manifest["metadata"]["annotations"]
    assert (annotations[ANNOTATION + "agent"], annotations[ANNOTATION + "on-behalf-of"]) == ("claude-code", "marta")


def test_large_agent_requests_go_to_a_person(platform):
    result = platform.request_environment(MARTAS_AGENT, "checkout", "load", "Load test", "large", 24)
    assert result["status"] == "pending_approval"
    approval = platform.cluster.approvals[result["approval_id"]]
    assert (approval["team"], approval["on_behalf_of"], approval["agent"]) == ("checkout", "marta", "claude-code")
    assert platform.record.events[-1]["action"] == "RequestNeedsApproval"


def test_an_autonomous_agent_works_only_for_its_owner_team(platform):
    assert platform.request_environment(CI_AGENT, "checkout", "nightly", "Nightly")["status"] == "accepted"
    annotations = platform.cluster.created[-1][0]["metadata"]["annotations"]
    assert annotations[ANNOTATION + "agent"] == "ci-agent" and ANNOTATION + "on-behalf-of" not in annotations
    with pytest.raises(Forbidden, match="ci-agent works for team checkout"):
        platform.request_environment(CI_AGENT, "payments", "nightly-2", "Nightly")


# --- Reads: use cases 9 and 10 -----------------------------------------------------------------

def test_reads_are_filtered_by_team(platform):
    assert {e["name"] for e in platform.list_environments(MARTAS_AGENT)} == {"checkout-dev", "agent-env"}
    assert {e["name"] for e in platform.list_environments(ANA)} == {"checkout-dev", "agent-env", "payments-dev"}
    assert platform.list_environments(MARTA, team="payments") == []
    with pytest.raises(Forbidden):
        platform.get_environment(MARTAS_AGENT, "payments-dev")
    with pytest.raises(NotFound):
        platform.get_environment(MARTA, "nope")


def test_service_and_quality_status_need_team_scope(platform):
    assert platform.service_status(MARTA, "orders-service", "checkout-dev")["state"] == "ready"
    with pytest.raises(Forbidden):
        platform.service_status(MARTA, "billing", "payments-dev")
    assert platform.quality_status(MARTAS_AGENT, "orders-service")["status"] == "passed"
    with pytest.raises(Forbidden, match="service billing belongs to payments"):
        platform.quality_status(MARTAS_AGENT, "billing")
    with pytest.raises(NotFound):
        platform.quality_status(MARTA, "ghost")


def test_approval_status_is_for_the_team(platform):
    result = platform.request_environment(MARTAS_AGENT, "checkout", "load", "Load test", "large", 24)
    assert platform.get_approval(MARTA, result["approval_id"])["status"] == "pending"
    assert "manifest" not in platform.get_approval(MARTA, result["approval_id"])
    with pytest.raises(Forbidden):
        platform.get_approval(LUIS_AGENT, result["approval_id"])


# --- Deploy and capabilities -----------------------------------------------------------------

def test_deploys_only_into_your_teams_environments(platform):
    assert platform.deploy_service(MARTAS_AGENT, "checkout-dev", "checkout-api")["status"] == "accepted"
    manifest, as_agent = platform.cluster.created[-1]
    assert (manifest["kind"], manifest["metadata"]["namespace"], as_agent) == ("SpringService", "env-checkout-dev", True)
    with pytest.raises(Forbidden):
        platform.deploy_service(MARTAS_AGENT, "payments-dev", "checkout-api")


def test_capabilities_in_your_teams_environments(platform):
    result = platform.request_capability(MARTAS_AGENT, "PostgresDatabase", "orders-db", "checkout-dev", {"size": "small"})
    assert result["status"] == "accepted" and result["namespace"] == "env-checkout-dev"
    with pytest.raises(Forbidden):
        platform.request_capability(MARTAS_AGENT, "PostgresDatabase", "orders-db", "payments-dev")
    with pytest.raises(NotFound, match="Available: PostgresDatabase"):
        platform.request_capability(MARTA, "Kafka", "events", "checkout-dev")


# --- Delete: use case 11 --------------------------------------------------------------------------

def test_agents_only_delete_what_an_agent_requested_for_the_same_person(platform):
    # Requested by Marta herself: her agent cannot delete it.
    with pytest.raises(Forbidden, match="requested by marta"):
        platform.delete_environment(MARTAS_AGENT, "checkout-dev")
    # Another team's environment.
    with pytest.raises(Forbidden, match="not payments"):
        platform.delete_environment(MARTAS_AGENT, "payments-dev")
    # Requested by an agent for Marta, but the agent of someone else on the team cannot either.
    stranger = MARTAS_AGENT.__class__("agent", "pedro", "codex", ("checkout",), (), "codex")
    with pytest.raises(Forbidden, match="requested for marta"):
        platform.delete_environment(stranger, "agent-env")
    with pytest.raises(Forbidden):
        platform.delete_environment(CI_AGENT, "agent-env")
    assert platform.cluster.deleted == []
    assert platform.delete_environment(MARTAS_AGENT, "agent-env")["status"] == "deleted"
    name, deletion, as_agent = platform.cluster.deleted[-1]
    assert (name, as_agent) == ("agent-env", True)
    assert deletion[ANNOTATION + "deleter-teams"] == "checkout"
    assert deletion[ANNOTATION + "deleted-on-behalf-of"] == "marta"


def test_people_delete_their_teams_environments(platform):
    assert platform.delete_environment(MARTA, "checkout-dev")["status"] == "deleted"
    with pytest.raises(Forbidden):
        platform.delete_environment(ANA, "payments-dev")


# --- Approvals: by role, for the team, with four eyes ----------------------------------------


def _large_request(platform, who=MARTAS_AGENT):
    return platform.request_environment(who, "checkout", "load-test", "load test", size="large")["approval_id"]


def test_an_approver_of_the_team_approves_and_the_platform_creates_it(platform):
    approval_id = _large_request(platform)
    result = platform.decide_approval(CARLOS, approval_id, "approve", "for the load test")
    assert result["status"] == "approved" and result["decided_by"] == "carlos"
    manifest, as_agent = platform.cluster.created[-1]
    assert manifest["metadata"]["annotations"]["platform.starterkit.dev/approved-by"] == "carlos"
    assert manifest["metadata"]["annotations"]["platform.starterkit.dev/on-behalf-of"] == "marta"
    assert as_agent is False, "the platform replays it as itself; only it may record approved-by"
    assert platform.record.events[-1]["action"] == "Approved"
    assert "carlos approved the request of claude-code for marta" in platform.record.events[-1]["message"]


def test_platform_team_approvers_approve_for_every_team(platform):
    approval_id = _large_request(platform)
    assert platform.decide_approval(ANA, approval_id, "reject", "too big")["status"] == "rejected"


@pytest.mark.parametrize("who, why", [
    (MARTA, "approver role"),
    (MARTA_APPROVER, "Four eyes"),
    (LUIS, "Team scope"),
    (MARTAS_AGENT, "Agents never approve"),
])
def test_who_cannot_decide(platform, who, why):
    approval_id = _large_request(platform)
    with pytest.raises(Forbidden, match=why):
        platform.decide_approval(who, approval_id, "approve")
    assert platform.cluster.approvals[approval_id]["status"] == "pending"


def test_luis_does_not_even_see_checkout_approvals(platform):
    approval_id = _large_request(platform)
    assert platform.list_approvals(LUIS) == []
    with pytest.raises(Forbidden, match="Team scope"):
        platform.get_approval(LUIS, approval_id)
    assert platform.record.events[-1]["action"] == "RequestNeedsApproval"


def test_four_eyes_can_be_switched_off(platform):
    platform.four_eyes = False
    approval_id = _large_request(platform)
    assert platform.decide_approval(MARTA_APPROVER, approval_id, "approve")["status"] == "approved"


def test_the_approval_says_who_may_decide(platform):
    approval_id = _large_request(platform)
    [for_marta] = platform.list_approvals(MARTA_APPROVER)
    assert (for_marta["can_decide"], "Four eyes" in for_marta["cannot_decide_reason"]) == (False, True)
    assert platform.get_approval(CARLOS, approval_id)["can_decide"] is True
    assert "manifest" not in for_marta


def test_a_decision_is_final(platform):
    from platform_api.service import Conflict

    approval_id = _large_request(platform)
    platform.decide_approval(ANA, approval_id, "reject")
    with pytest.raises(Conflict, match="already rejected"):
        platform.decide_approval(CARLOS, approval_id, "approve")


def test_denied_decisions_are_recorded(platform):
    approval_id = _large_request(platform)
    with pytest.raises(Forbidden):
        platform.decide_approval(LUIS, approval_id, "approve")
    # Luis cannot read it: team scope first.
    approval_id2 = platform.request_environment(LUIS_AGENT, "payments", "big", "x", size="large")["approval_id"]
    with pytest.raises(Forbidden):
        platform.decide_approval(MARTA_APPROVER, approval_id2, "approve")
    with pytest.raises(Forbidden):
        platform.decide_approval(LUIS, approval_id2, "approve")
    assert platform.record.events[-1]["action"] == "ApprovalDenied"


def test_overview_is_for_your_teams(platform):
    _large_request(platform)
    mine = platform.overview(MARTA)
    assert {e["name"] for e in mine["environments"]} == {"checkout-dev", "agent-env"}
    assert [s["name"] for s in mine["services"]] == ["orders-service"]
    assert {a["subject"] for a in mine["activity"]} <= {"checkout-dev", "agent-env", "load-test"}
    assert mine["metrics"]["pending_approvals"] == 1
    everything = platform.overview(ANA)
    assert everything["scope"] == "all teams" and len(everything["environments"]) == 3
    assert platform.overview(LUIS)["approvals"] == []
