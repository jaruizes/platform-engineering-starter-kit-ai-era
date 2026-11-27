import copy

import pytest

from platform_api import proposals
from platform_api.golden_paths import InvalidRequest
from platform_api.git_server import RepositoryExists
from platform_api.service import Forbidden

SPRING = {"name": "loyalty-points", "description": "Loyalty points", "owner": "checkout", "module": "points",
          "environment": "checkout-dev"}


def test_creates_the_repository_and_records_who_asked(platform):
    result = platform.create_repository("spring-service", SPRING, "agent:claude-code")
    assert result["repository"] == "http://localhost:3000/platform/loyalty-points"
    assert result["catalogEntity"] == "component:default/loyalty-points"
    description, files, message = platform.git.repositories["loyalty-points"]
    assert description == "Loyalty points"
    assert "Requested-by: agent:claude-code" in message
    assert any(f.path == "catalog-info.yaml" for f in files)
    event = platform.record.events[-1]
    assert (event["action"], event["actor"], event["kind"]) == ("RequestAccepted", "agent:claude-code", "Component")
    assert "for team checkout" in event["message"]


def test_the_same_request_from_any_channel_gives_the_same_repository(platform):
    by_agent = platform.create_repository("spring-service", SPRING, "agent:claude-code")
    by_person = platform.create_repository("spring-service", {**SPRING, "name": "loyalty-points-2"}, "user:default/ana")
    agent_files = {f.path for f in platform.git.repositories[by_agent["name"]][1]}
    person_files = {f.path.replace("loyaltypoints2", "loyaltypoints") for f in platform.git.repositories[by_person["name"]][1]}
    assert agent_files == person_files


def test_rejects_unknown_golden_paths_and_existing_repositories(platform):
    with pytest.raises(InvalidRequest, match="no code Golden Path 'cobol'"):
        platform.create_repository("cobol", {}, "agent:claude-code")
    platform.create_repository("spring-service", SPRING, "agent:claude-code")
    with pytest.raises(RepositoryExists):
        platform.create_repository("spring-service", SPRING, "agent:claude-code")
    assert platform.record.events[-1]["action"] == "RequestFailed"


def test_people_propose_capabilities(platform, postgres_definition):
    definition = copy.deepcopy(postgres_definition)
    definition["metadata"]["name"] = "redis-cache"
    result = platform.propose_capability(definition, "user:default/ana", "Ana")
    proposal = platform.git.proposals[0]
    assert proposal["repository"] == "platform-starter-kit"
    assert proposal["path"] == "platform/capabilities/infrastructure/redis-cache/capability.yaml"
    assert "proposed by Ana through the platform" in proposal["body"]
    assert result["entityRef"] == "resource:default/redis-cache.pr-1"
    assert platform.record.events[-1]["action"] == "CapabilityProposed"


def test_agents_do_not_propose_capabilities(platform, postgres_definition):
    with pytest.raises(Forbidden):
        platform.propose_capability(postgres_definition, "agent:claude-code")
    assert platform.git.proposals == []


def test_invalid_definitions_are_not_proposed(platform, postgres_definition):
    definition = copy.deepcopy(postgres_definition)
    del definition["spec"]["acceptance"]
    with pytest.raises(proposals.InvalidDefinition, match="acceptance"):
        platform.propose_capability(definition, "user:default/ana")
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
