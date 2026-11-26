---
name: api-to-mcp
description: Use when a user wants to consume an existing REST business API from Claude Code using natural language, without a frontend or direct database access.
---

# API to MCP Golden Path

1. Confirm the Spring business API already exists and works in an ephemeral environment. Do **not** create a second DB or redeploy the backend for Zero-UI.
2. Read its committed `contracts/openapi.yaml` and verify GET endpoints through port-forward.
3. Call platform MCP `create_api_mcp_adapter(name, description, team, backend_service, environment)`.
4. Clone the returned Gitea repo. Replace its sample `operations.json` with reviewed, fixed GET paths and explicitly typed query parameters. For Retail use `examples/scenarios/example/data/retail-operations.json`.
5. Run `pytest -q`. Run backend `kubectl -n env-<environment> port-forward svc/<backend_service> 18080:80`.
6. Register the generated executable as a **local stdio MCP server** in Claude Code, using the instructions in the generated README.
7. Ask questions; select tools and return only grounded results. Format cents as euros. Cite date filters. Reject unknown operations, write actions, arbitrary URLs or SQL.
8. Explain limitations honestly: this is local Zero-UI, not production identity delegation or an agent runtime in Kubernetes.

Do not expose database credentials, use arbitrary SQL, or work around backend authorization.
