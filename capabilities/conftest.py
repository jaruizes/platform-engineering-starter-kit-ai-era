"""Fixtures shared by the acceptance tests of every capability."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "tools"))

import e2e  # noqa: E402


@pytest.fixture(params=["human", "agent"])
def requester(request):
    """Runs a test twice: as a person (kubectl) and as an agent (platform MCP server)."""
    return e2e.Human() if request.param == "human" else e2e.Agent()


@pytest.fixture
def human():
    return e2e.Human()


@pytest.fixture
def agent():
    return e2e.Agent()


@pytest.fixture(scope="module")
def environment():
    """An ephemeral environment for the tests of one capability, deleted afterwards."""
    name, namespace = e2e.environment()
    yield namespace
    e2e.delete_environment(name)
