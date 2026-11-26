"""Two stable tools for discovering and querying approved REST operations.

The same MCP adapter supports local stdio and in-cluster Streamable HTTP. It NEVER talks to PostgreSQL or
accepts arbitrary SQL, URL, HTTP method, or credentials from the LLM.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .bridge import ContractError, load_contract, query_api

FILE = Path(os.environ.get("MCP_OPERATIONS_FILE", str(Path(__file__).resolve().parents[1] / "operations.json")))
CONTRACT = load_contract(FILE)
mcp = MCPServer(name="rest-api-adapter", instructions=(
    "Use list_api_operations to discover approved business queries. "
    "Call query_api with one exact operation name and typed parameters. "
    "Never invent a business metric, SQL query or endpoint."
))


@mcp.tool()
def list_api_operations() -> list[dict[str, Any]]:
    """Lists the permitted read-only operations, descriptions and parameter contracts."""
    return CONTRACT["operations"]


@mcp.tool()
def query_api_operation(operation: str, parameters: dict[str, Any] | None = None) -> Any:
    """Invokes an approved read-only API operation with validated query parameters."""
    try:
        return query_api(CONTRACT, operation, parameters or {})
    except (ContractError, RuntimeError) as exc:
        # These are curated adapter errors, never raw HTTP bodies or credentials.
        raise ToolError(str(exc)) from exc


def runtime_options() -> dict[str, Any]:
    """The endpoint is private; port-forward, never public ingress, for the MVP."""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        return {"transport": "stdio"}
    if transport == "streamable-http":
        port = int(os.getenv("MCP_PORT", "8080"))
        if not 1 <= port <= 65535:
            raise ValueError("MCP_PORT must be between 1 and 65535")
        # No session affinity required; supports independent Claude Code clients.
        return {
            "transport": "streamable-http",
            "host": "0.0.0.0",
            "port": port,
            "streamable_http_path": "/mcp",
            "stateless_http": True,
            "json_response": True,
        }
    raise ValueError("MCP_TRANSPORT must be 'stdio' or 'streamable-http'")


def main() -> None:
    mcp.run(**runtime_options())


if __name__ == "__main__":
    main()
