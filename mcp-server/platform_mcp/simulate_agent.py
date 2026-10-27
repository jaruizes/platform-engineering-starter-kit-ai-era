"""A scripted agent for the demo, for when there is no AI agent at hand.

It talks to the platform MCP server exactly like a coding agent would and
walks through the demo scenario: a small environment is granted, a large
one goes to a human, and an out-of-policy one is stopped.

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

URL = os.environ.get("MCP_URL", "http://localhost:8081/mcp")
CONSOLE_URL = os.environ.get("CONSOLE_URL", "http://localhost:8080")

STEPS = [
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
    for key in ("status", "namespace", "url", "approval_id", "reason", "next_step"):
        if isinstance(data, dict) and data.get(key):
            print(f"   {key}: {data[key]}")


async def main() -> None:
    # The token of the platform MCP server, when it has one (on AWS).
    token = os.environ.get("MCP_TOKEN")
    client = httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"} if token else None,
        timeout=httpx2.Timeout(30, read=300),
    )
    async with client, streamable_http_client(URL, http_client=client) as streams:
        read, write = streams[0], streams[1]
        info = types.Implementation(name=os.environ.get("AGENT_NAME", "demo-agent"), version="1.0")
        async with ClientSession(read, write, client_info=info) as session:
            await session.initialize()
            for said, tool, args in STEPS:
                print(f'\nAgent: "{said}"\n-> {tool}({", ".join(f"{k}={v!r}" for k, v in args.items())})')
                _print_result(await session.call_tool(tool, args))
                await asyncio.sleep(1)
    print(f"\nOpen the console at {CONSOLE_URL} to see it all, and approve or reject the load test.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
