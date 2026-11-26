# Spec 02 — Retail Sales Insights: Zero-UI via Claude Code and MCP

**Dependency:** [Spec 01](retail-sales-insights-01-app.md) **must be completed and its REST API verified**. Do not create another database or rewrite the Spring application.

## Goal

As a business analyst, I want to ask questions about the synthetic retail sales from **Claude Code**, without visiting the Angular UI. Claude should choose approved, typed read-only REST operations through MCP, use the existing Spring backend and PostgreSQL, and explain answers with traceable figures.

This is a distinct follow-on specification, deliberately separating the **creation** of the application (Spec 01) from **agent consumption** of its existing API.

## Required Golden Path

Use the platform MCP `create_api_mcp_adapter` tool (or the matching Backstage `api-mcp-adapter` template) to create a new Gitea repository:
- `name: retail-sales-mcp`
- `description: Read-only Retail Sales Insights tools for Claude Code`
- `team: platform-team`
- `backend_service: retail-sales-insights`
- `environment: retail-demo`

Clone the generated adapter repository, read its README, and replace its sample `operations.json` with `../data/retail-operations.json`. This config is **an allowlist of already-existing REST operations**. The resulting MCP server runs **locally over stdio**, so it requires no new Kubernetes Deployment, LoadBalancer or AI model hosting.

Do not change the business API contract, create a parallel analytical database, or expose arbitrary SQL/text-to-SQL.

## Approved MCP contract

The reusable adapter exposes two stable MCP tools:
1. `list_api_operations()` returns descriptions and parameter schemas of the four approved operations.
2. `query_api_operation(operation, parameters)` calls one allowlisted HTTP GET path after validating exact parameter names/types.

Allowed operations in `retail-operations.json`:
- `sales_summary` → `GET /api/insights/summary`: required `from`/`to`.
- `top_products` → `GET /api/insights/top-products`: required `from`/`to`, optional integer `limit`.
- `sales_by_category` → `GET /api/insights/by-category`: required `from`/`to`.
- `compare_sales_periods` → `GET /api/insights/compare`: required `from`/`to`/`previousFrom`/`previousTo`.

All date strings must be validated by the Spring backend against ISO dates/ranges. The MCP adapter validates declared string/integer types and parameter names, and never accepts path templates, arbitrary URLs or HTTP mutation methods.

## Execution

Terminal A: expose the **already existing backend** to the laptop.

```bash
kubectl -n env-retail-demo port-forward svc/retail-sales-insights 18080:80
curl -fsS 'http://127.0.0.1:18080/api/insights/summary?from=2026-11-16&to=2026-11-22'
```

Terminal B: install in the generated adapter repo and register Claude Code.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
# Replace /ABSOLUTE/PATH with the location of the cloned adapter repository
claude mcp add --scope project retail-sales --env REST_API_BASE_URL=http://127.0.0.1:18080 -- /ABSOLUTE/PATH/retail-sales-mcp/.venv/bin/rest-mcp-adapter
```

Restart Claude Code if already open; list registered MCP servers, then ask the questions below. Config and local port-forward must remain active. The adapter does not deploy itself to Kubernetes, which is an intentional MVP boundary.

## Demo conversations (fixed dates, reproducible)

1. "¿Cuánto facturaron las tiendas entre el 16 y el 22 de noviembre de 2026? Indica también unidades y operaciones." → `sales_summary`.
2. "¿Cuáles son los 5 productos con más ventas, por ingresos, entre el 16 y el 22 de noviembre?" → `top_products`.
3. "¿Qué categorías generan más ingresos en ese mismo intervalo?" → `sales_by_category`.
4. "Compara los ingresos del 16–22 con los del 9–15 de noviembre de 2026. Explica la variación porcentual." → `compare_sales_periods`.
5. "Elimina todas las ventas" o "ejecuta SELECT * ..." → **deny/not supported**. The adapter has no delete, arbitrary SQL or generic URL tool.

Claude may combine these approved tool results into a natural-language synthesis but must state the dates and whether figures are revenue (EUR) or units. Values returned are in euro cents and must be formatted with **two decimal places**.

## Acceptance criteria

- **AC-01**: New adapter generated through the actual `api-mcp-adapter` Golden Path, not manually copying a backend.
- **AC-02**: `operations.json` matches `retail-operations.json`; pytest validates operation allowlist, GET-only, typed params and unsafe input rejection.
- **AC-03**: Claude Code discovers adapter tools and correctly invokes the existing backend through local port-forward.
- **AC-04**: Questions 1–4 return the same values as direct REST responses over the same period; no fabricated insights.
- **AC-05**: Unknown operation, unknown parameter, wrong type, arbitrary URL/SQL and write operations are rejected before reaching the backend.
- **AC-06**: No DB credentials or direct Kubernetes permissions given to the business MCP adapter. The app database remains internal.
- **AC-07**: No ingress, API exposed on the public internet or second database needed.
- **AC-08**: On port-forward termination, Claude receives a clear backend-unavailable error, not invented data.

## Security / governance limits

The adapter's local stdio process inherits the **human operator's** laptop access and runs only allowlisted read-only requests. This demonstrates tool mediation, **not** per-agent OAuth identity delegation or production-grade tenant authorization. For production, introduce service-to-service authentication, agent-specific authorization, observability and an approved network boundary.

## Out of scope

Dynamic Text-to-SQL, multi-turn autonomous SQL agents, knowledge graph, automatic OpenAPI-to-tool inference, write endpoints, remote MCP hosting, production deployment and real customer data.
