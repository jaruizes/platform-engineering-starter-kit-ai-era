import asyncio
import json

from starlette.responses import PlainTextResponse

from platform_mcp import platform_api_client as api
from platform_mcp.mcp_server import OAuthResource

ISSUER = "http://localhost:8180/realms/platform"


async def ok(scope, receive, send):
    await PlainTextResponse("ok")(scope, receive, send)


def validate(token):
    if token != "good":
        raise api.RequestFailed("Invalid token: Signature has expired", 401)
    return {"kind": "agent"}


def call(app, path, authorization=None):
    headers = [(b"authorization", authorization.encode())] if authorization else []
    scope = {"type": "http", "method": "POST", "path": path, "headers": headers, "query_string": b""}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    start = sent[0]
    body = b"".join(m.get("body", b"") for m in sent[1:])
    return start["status"], dict(start["headers"]), body


def resource():
    return OAuthResource(ok, "http://localhost:8081/mcp", ISSUER, validate)


def test_without_a_token_the_client_is_told_where_to_sign_in():
    status, headers, _ = call(resource(), "/mcp")
    assert status == 401
    assert headers[b"www-authenticate"] == (
        b'Bearer resource_metadata="http://localhost:8081/.well-known/oauth-protected-resource"')


def test_publishes_the_protected_resource_metadata():
    status, _, body = call(resource(), "/.well-known/oauth-protected-resource/mcp")
    metadata = json.loads(body)
    assert status == 200
    assert metadata["resource"] == "http://localhost:8081/mcp"
    assert metadata["authorization_servers"] == [ISSUER]


def test_invalid_tokens_are_rejected_and_valid_ones_pass():
    app = resource()
    status, headers, body = call(app, "/mcp", "Bearer expired")
    assert status == 401 and b'error="invalid_token"' in headers[b"www-authenticate"]
    assert b"Signature has expired" in body
    assert call(app, "/mcp", "Bearer good")[0] == 200
    assert call(app, "/healthz")[0] == 200
