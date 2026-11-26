# ${{ values.name }} — REST to MCP (Zero-UI)

${{ values.description }}

This adapter is created by the Platform Engineering API-to-MCP Golden Path.
It exposes *only* fixed read-only endpoints declared in `operations.json`.
Backend: `${{ values.backendService }}`. Environment: `${{ values.environment }}`.
The adapter runs on the Claude Code machine through MCP **stdio**; it is not
a Kubernetes service or an internet-facing server.

## Connect to an existing backend

First edit `operations.json` to match approved GET endpoints in the backend's
OpenAPI contract. Avoid arbitrary SQL, user-controlled URLs, and write actions.
The example `/api/health` must be replaced for the Retail demo.

With the platform running, use a second terminal:

```bash
kubectl -n env-${{ values.environment }} port-forward svc/${{ values.backendService }} 18080:8080
```

Check one API endpoint with `curl http://127.0.0.1:18080/api/insights/summary?from=2026-11-16\&to=2026-11-22`.

Install and test:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

From the adapter repository, register the stdio process in Claude Code (absolute
path recommended to avoid CWD ambiguity):

```bash
claude mcp add --scope project retail-insights --env REST_API_BASE_URL=http://127.0.0.1:18080 -- /absolute/path/to/adapter/.venv/bin/rest-mcp-adapter
```

Restart/reload Claude Code after registering. Ask it to list the approved
operations and answer business questions grounded in the results.

## Security / limits

- REST endpoints must start with `/api/`, use GET and have an explicit allowlist.
- Only typed query parameters are permitted; path substitution is not supported.
- The backend, not the adapter, owns authorization, validation and business logic.
- The default HTTP base URL is loopback-only. A remote backend requires HTTPS.
- For protected APIs set `REST_API_BEARER_TOKEN` locally; do not commit secrets.
- The adapter does not provide production-grade multi-tenant identity delegation.
- Database access remains in Spring Boot; MCP cannot read SQL directly.
