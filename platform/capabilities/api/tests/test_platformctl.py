"""platformctl is a thin channel: it sends the request and shows the answer."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("platformctl", ROOT / "platform/access/cli/platformctl.py")
platformctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platformctl)


def test_create_sends_the_parameters_and_who_asks(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(platformctl, "call", lambda method, path, body=None: sent.append((method, path, body))
                        or {"status": "created"})
    monkeypatch.setenv("PLATFORM_USER", "user:default/ana")
    platformctl.main(["create", "spring-service", "name=loyalty-points", "description=Loyalty points"])
    assert sent == [("POST", "/v1/golden-paths/spring-service/repositories", {
        "parameters": {"name": "loyalty-points", "description": "Loyalty points"},
        "requester": "user:default/ana"})]
    assert json.loads(capsys.readouterr().out)["status"] == "created"


def test_propose_reads_the_definition(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(platformctl, "call", lambda method, path, body=None: sent.append(body) or {})
    monkeypatch.setenv("PLATFORM_USER", "user:default/ana")
    definition = ROOT / "platform/capabilities/infrastructure/postgres-database/capability.yaml"
    platformctl.main(["propose", str(definition), "--name", "Ana"])
    assert sent[0]["definition"]["metadata"]["name"] == "postgres-database"
    assert sent[0]["requesterName"] == "Ana"


def test_rejects_parameters_without_a_value():
    with pytest.raises(SystemExit, match="key=value"):
        platformctl.main(["create", "spring-service", "loyalty-points"])
