import json
import pytest
from rest_mcp_adapter.bridge import ContractError, load_contract, validate_parameters, query_api


def contract(tmp_path):
    path = tmp_path / "operations.json"
    path.write_text(json.dumps({"operations": [{"name": "top_products", "method": "GET",
        "path": "/api/insights/top-products", "parameters": {
            "limit": {"type": "integer", "required": True},
            "from": {"type": "string", "required": True},
        }}]}))
    return load_contract(path)


def test_allowlisted_operations_and_types(tmp_path):
    c = contract(tmp_path)
    assert validate_parameters(c["operations"][0], {"limit": 5, "from": "2026-11-01"}) == {
        "limit": "5", "from": "2026-11-01"}
    with pytest.raises(ContractError):
        validate_parameters(c["operations"][0], {"limit": "5", "from": "2026-11-01"})
    with pytest.raises(ContractError):
        validate_parameters(c["operations"][0], {"limit": 5, "from": "2026-11-01", "sql": "DROP"})


@pytest.mark.parametrize("method,path", [("POST", "/api/insights"), ("GET", "http://127.0.0.1/secret"),
    ("GET", "/admin/secrets"), ("GET", "/api/../secrets")])
def test_reject_unsafe_contract(tmp_path, method, path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({"operations": [{"name": "unsafe", "method": method,
        "path": path, "parameters": {}}]}))
    with pytest.raises(ContractError):
        load_contract(f)


def test_reject_non_allowlisted_operation(tmp_path):
    with pytest.raises(ContractError):
        query_api(contract(tmp_path), "execute_sql", {}, "http://127.0.0.1:18080")


def test_reject_remote_http(tmp_path):
    with pytest.raises(ContractError):
        query_api(contract(tmp_path), "top_products",
            {"limit": 5, "from": "2026-11-01"}, "http://example.org")


def test_constructs_encoded_query_from_fixed_path(tmp_path, monkeypatch):
    from rest_mcp_adapter import bridge

    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def read(self, size):
            return b'{"revenueCents":91641}'

    received = []

    def fake_open(req, timeout):
        received.append((req.full_url, req.get_method(), req.get_header("Authorization"), timeout))
        return FakeResponse()

    monkeypatch.setattr(bridge, "urlopen", fake_open)
    result = query_api(contract(tmp_path), "top_products",
        {"from": "2026-11-16", "limit": 5}, "http://127.0.0.1:18080", token="test-token")
    assert result == {"revenueCents": 91641}
    assert received == [(
        "http://127.0.0.1:18080/api/insights/top-products?limit=5&from=2026-11-16",
        "GET", "Bearer test-token", 10,
    )]


def test_mcp_v2_server_can_be_imported():
    from rest_mcp_adapter import server
    assert server.mcp is not None
    assert server.CONTRACT["operations"][0]["name"] == "health"
