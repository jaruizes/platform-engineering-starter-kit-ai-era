import asyncio

from starlette.responses import PlainTextResponse

from platform_mcp.mcp_server import BearerToken


async def ok(scope, receive, send):
    await PlainTextResponse("ok")(scope, receive, send)


def call(app, path: str, authorization: str | None = None) -> int:
    headers = [(b"authorization", authorization.encode())] if authorization else []
    scope = {"type": "http", "method": "GET", "path": path, "headers": headers, "query_string": b""}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent[0]["status"]


def test_requests_need_the_token():
    app = BearerToken(ok, "s3cret")
    assert call(app, "/mcp") == 401
    assert call(app, "/mcp", "Bearer wrong") == 401
    assert call(app, "/mcp", "Bearer s3cret") == 200


def test_health_check_needs_no_token():
    assert call(BearerToken(ok, "s3cret"), "/healthz") == 200
