"""Acceptance tests for the postgres-database capability.

One test per acceptance criterion in capability.yaml, named after its id
(test_ac_<n>_...). Criteria checked "as: both" run as a person (kubectl) and
as an AI agent (platform MCP server). They need a platform from `make up`.
"""

import base64

import pytest

import e2e

KIND, PLURAL = "PostgresDatabase", "postgresdatabases"
RESOURCE = f"{PLURAL}.{e2e.GROUP}"


def connection(namespace: str, name: str) -> dict[str, str] | None:
    secret = e2e.get("secret", f"{name}-connection", namespace)
    if not secret:
        return None
    return {k: base64.b64decode(v).decode() for k, v in secret.get("data", {}).items()}


def ready(namespace: str, name: str) -> bool:
    db = e2e.get(RESOURCE, name, namespace) or {}
    return any(c["type"] == "Ready" and c["status"] == "True" for c in db.get("status", {}).get("conditions", []))


def query(namespace: str, conn: dict[str, str], sql: str = "select 1"):
    """Runs a query from a new pod. It retries for a while: a new pod's network
    policies can take a few seconds to include it."""
    script = 'for i in 1 2 3 4 5 6; do psql -tAc "$SQL" && exit 0; sleep 3; done; exit 1'
    return e2e.run_pod(
        namespace, "postgres:17-alpine", ["sh", "-c", script],
        env={"PGHOST": conn["host"], "PGPORT": conn["port"], "PGUSER": conn["username"],
             "PGDATABASE": conn["database"], "PGPASSWORD": conn["password"], "PGCONNECT_TIMEOUT": "5", "SQL": sql},
        timeout=180,
    )


def delete(namespace: str, name: str) -> None:
    e2e.kubectl("delete", RESOURCE, name, "-n", namespace, "--ignore-not-found", "--wait=true", "--timeout=120s")


def test_ac_1_small_database_is_ready_with_a_working_connection(environment, requester):
    """AC-1: a small database is ready within 3 minutes and its Secret opens a working connection."""
    name = e2e.unique("db")
    outcome = requester.request(KIND, PLURAL, environment, name, {"size": "small"})
    assert outcome.status == "created", outcome.reason
    try:
        e2e.wait_for(f"database {name} to be ready", lambda: ready(environment, name), timeout=180)
        conn = connection(environment, name)
        assert conn is not None
        assert set(conn) >= {"host", "port", "database", "username", "password"}
        result = query(environment, conn)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith("1")
    finally:
        delete(environment, name)


@pytest.mark.parametrize("size", ["medium", "large"])
def test_ac_2_agent_needs_approval_for_bigger_databases(environment, agent, size):
    """AC-2: an agent asking for medium or large gets a human approval request, and nothing is created."""
    name = e2e.unique("db")
    outcome = agent.request(KIND, PLURAL, environment, name, {"size": size})
    assert outcome.status == "pending_approval", outcome.raw
    assert "Human approval required" in outcome.reason
    assert e2e.get(RESOURCE, name, environment) is None


def test_ac_3_rejected_outside_an_environment(human):
    """AC-3: a database outside an ephemeral environment is rejected with the rule explained."""
    outcome = human.request(KIND, PLURAL, "default", e2e.unique("db"), {"size": "small"})
    assert outcome.status == "denied"
    assert "[GR-1]" in outcome.reason and "ephemeral environments" in outcome.reason


def test_ac_4_third_database_is_over_budget(environment, human):
    """AC-4: an environment with 2 databases rejects a third one, explaining the budget."""
    names = [e2e.unique("db"), e2e.unique("db")]
    try:
        for name in names:
            outcome = human.request(KIND, PLURAL, environment, name, {"size": "small"})
            assert outcome.status == "created", outcome.reason
        outcome = human.request(KIND, PLURAL, environment, e2e.unique("db"), {"size": "small"})
        assert outcome.status == "denied"
        assert "[GR-2]" in outcome.reason and "budget" in outcome.reason
    finally:
        for name in names:
            delete(environment, name)


def test_ac_5_unreachable_from_another_environment(environment, human):
    """AC-5: a pod in another environment cannot connect to the database."""
    name = e2e.unique("db")
    other_name, other = e2e.environment()
    try:
        outcome = human.request(KIND, PLURAL, environment, name, {"size": "small"})
        assert outcome.status == "created", outcome.reason
        e2e.wait_for(f"database {name} to be ready", lambda: ready(environment, name), timeout=180)
        conn = connection(environment, name)
        assert query(environment, conn).returncode == 0, "the database must work from its own environment"
        result = query(other, conn)
        assert result.returncode != 0, "a pod in another environment could connect"
    finally:
        delete(environment, name)
        e2e.delete_environment(other_name)


def test_ac_6_deleting_leaves_nothing_behind(environment, human):
    """AC-6: deleting the request deletes the database, its storage and its Secret."""
    name = e2e.unique("db")
    outcome = human.request(KIND, PLURAL, environment, name, {"size": "small"})
    assert outcome.status == "created", outcome.reason
    e2e.wait_for(f"database {name} to be ready", lambda: ready(environment, name), timeout=180)
    delete(environment, name)
    server = f"{name}-postgres"
    leftovers = [
        ("deployment", server), ("service", server), ("networkpolicy", server),
        ("persistentvolumeclaim", f"{server}-data"), ("secret", f"{name}-connection"),
    ]
    e2e.wait_for(
        "every part of the database to be deleted",
        lambda: all(e2e.get(kind, obj, environment) is None for kind, obj in leftovers),
        timeout=120,
    )
