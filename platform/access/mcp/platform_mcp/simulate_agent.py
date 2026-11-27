"""A scripted agent for the demo, for when there is no AI agent at hand.

It talks to the platform MCP server exactly like a coding agent would and
walks through the demo scenario: a small environment is granted, another
team's is refused, a large one goes to a human, and an out-of-policy one is
stopped. It is the autonomous agent ci-agent of team checkout: it signs in
to Keycloak with its own client credentials, so the platform knows who it is
without trusting anything it says about itself.

Run it inside the cluster:  make demo-agent
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from .platform_api_client import client_credentials_token

URL = os.environ.get("MCP_URL", "http://localhost:8081/mcp")
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://localhost:8080")
PORTAL_URL = os.environ.get("PORTAL_URL", "http://localhost:7007")

STEPS = [
    ("Who does the platform think I am?", "whoami", {}),
    ("Which Golden Paths does this platform offer?", "list_golden_paths", {}),
    (
        "I need an environment to test this change.",
        "request_environment",
        {"team": "checkout", "name": "pr-123", "purpose": "Test the new discount rules (PR 123)"},
    ),
    (
        "Deploy the service into it.",
        "deploy_service",
        {"environment": "pr-123", "name": "checkout-api"},
    ),
    (
        "And one for the payments team, while I am at it.",
        "request_environment",
        {"team": "payments", "name": "pay-test", "purpose": "Try something in payments"},
    ),
    (
        "Now a large environment for a load test.",
        "request_environment",
        {
            "team": "checkout",
            "name": "load-test",
            "purpose": "Load test the checkout flow before Black Friday",
            "size": "large",
            "ttl_hours": 24,
        },
    ),
    (
        "And one that lives for two weeks.",
        "request_environment",
        {"team": "checkout", "name": "long-lived", "purpose": "Keep it around", "ttl_hours": 336},
    ),
]


def _print_result(result: types.CallToolResult) -> None:
    if result.structured_content is not None:
        data = result.structured_content.get("result", result.structured_content)
    else:
        data = [json.loads(c.text) for c in result.content if isinstance(c, types.TextContent)]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "kind" in data[0]:
        for path in data:
            print(f"   - {path['name']}: {path['description']}")
        return
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    for key in ("kind", "agent", "teams", "status", "namespace", "url", "approval_id", "reason", "next_step"):
        if isinstance(data, dict) and data.get(key):
            print(f"   {key}: {data[key]}")


async def main() -> None:
    # Its own access token from Keycloak (client credentials).
    token = os.environ.get("MCP_TOKEN") or client_credentials_token()
    client = httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx2.Timeout(30, read=300),
    )
    async with client, streamable_http_client(URL, http_client=client) as streams:
        read, write = streams[0], streams[1]
        info = types.Implementation(name=os.environ.get("AGENT_NAME", "ci-agent"), version="1.0")
        async with ClientSession(read, write, client_info=info) as session:
            await session.initialize()
            for said, tool, args in STEPS:
                print(f'\nAgent: "{said}"\n-> {tool}({", ".join(f"{k}={v!r}" for k, v in args.items())})')
                _print_result(await session.call_tool(tool, args))
                await asyncio.sleep(1)
    print(f"\nSee it all in the console ({CONSOLE_URL}). To approve or reject the load test, sign in to the "
          f"portal ({PORTAL_URL}, AI Platform page) as an approver of checkout: carlos, or ana (platform-team), "
          "or use platformctl approve <id>.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
