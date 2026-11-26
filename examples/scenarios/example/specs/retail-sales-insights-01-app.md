# Spec 01 — Retail Sales Insights: Spring API + Angular dashboard

**Status:** ready for implementation by a coding agent · **depends on:** Starter Kit (platform MCP, portal MCP, Spring/Angular Golden Paths, ephemeral environments, PostgreSQL, Gitea/Argo CD). **No MCP business adapter yet**; that is Spec 02.

## Goal and bounded scope

As a retail manager, I want to inspect sales KPIs for a synthetic chain of three stores through a minimal browser dashboard. Build an independently deployed Spring Boot service `retail-sales-insights` and an Angular app `retail-sales-web`, using **existing platform Golden Paths**, not manually provisioning Kubernetes resources. No external API or user/customer personal data. Use the fixed demo dataset in `../data/`.

This spec describes an application to **be generated and implemented by an agent**; the files under `data/` are its authoritative reproducible fixture. It is not a claim that the resulting application is already deployed.

## Platform journey (mandatory order)

1. Read the backend Spring v2 and frontend Angular v1 engineering standards from the **portal MCP**.
2. Call platform MCP `request_environment(team="retail",name="retail-demo",purpose="Retail sales dashboard demo",size="small",ttl_hours=8)`; wait for Ready using `get_environment`.
3. Call `create_service(name="retail-sales-insights",description="Retail sales metrics over synthetic orders",team="platform-team",module="sales",environment="retail-demo")`. The built-in Spring Golden Path already declares `PostgresDatabase retail-sales-insights-db` and maps DB credentials into the service. **Do not request a second database.** If the environment quota requires resizing, ask rather than bypass policy.
4. Clone the returned Gitea repository, read its `AGENTS.md`, preserve the hexagonal module organization, implement the business API and Flyway migrations; run local tests before pushing.
5. Call `create_angular_app(name="retail-sales-web",description="Sales metrics dashboard",team="platform-team",environment="retail-demo",backend_service="retail-sales-insights")`. This Golden Path configures Nginx to proxy **same-origin** `/api/` to the backend within the namespace. Implement UI and tests; do not hardcode a cluster address in the browser.
6. Push code to each generated Gitea repository `main`, monitor both through `get_service_status`. Verify quality gates before presenting results.

**Important:** `team` is the MCP logical owner and must correspond to an existing Backstage Group (`platform-team` in the starter kit). The environment's `team="retail"` is its budget owner; do not silently assume it exists in the catalog.

## Data contract — exact and deterministic

Files supplied in `../data/`:
- `V1__create_sales_schema.sql`: Flyway DDL: `products`, `stores`, `sales`, foreign keys and useful indexes.
- `V2__seed_demo_sales.sql`: full SQL INSERT fixture suitable for Flyway (no external CSV loader).
- `sales.csv`: equivalent sales data for inspection and validation; **SQL is the runtime source**.

Copy the two SQL files to `retail-sales-insights/src/main/resources/db/migration/` in their filename order. Do not generate alternative random fixtures. Keep monetary values in **integer euro cents**; never use floating-point amounts for aggregation. Date range covers 2026-10-26 through 2026-11-22 inclusive (four Monday–Sunday weeks), and every query is parameterized by explicit dates; no dependence on today's date or relative-time clock.

Schema:
- `products(id BIGINT PK, sku VARCHAR(32) UNIQUE, name VARCHAR(100), category VARCHAR(60))`.
- `stores(id BIGINT PK, name VARCHAR(100), city VARCHAR(60))`.
- `sales(id BIGINT PK, product_id FK, store_id FK, sold_at DATE, quantity INTEGER CHECK > 0, unit_price_cents INTEGER CHECK >= 0)`.
- Revenue = `SUM(quantity * unit_price_cents)`. Each sale is a line item, not an order with taxes or discounts.

## REST contract — implement and document in `contracts/openapi.yaml`

All dates are ISO `YYYY-MM-DD`, inclusive; reject invalid dates, reversed ranges and unknown parameters with HTTP 400. JSON returns cents and counts; JSON keys must match exactly.

| Method & path | Parameters | Response |
|---|---|---|
| `GET /api/insights/summary` | `from`, `to` | `{from,to,revenueCents,salesCount,unitsSold}` |
| `GET /api/insights/top-products` | `from`, `to`, `limit` (default 5, max 10) | `{from,to,items:[{productId,productName,category,revenueCents,unitsSold}]}` |
| `GET /api/insights/by-category` | `from`, `to` | `{from,to,items:[{category,revenueCents,unitsSold}]}` |
| `GET /api/insights/compare` | `from`, `to`, `previousFrom`, `previousTo` | `{currentRevenueCents,previousRevenueCents,changePercent}` |

Sorting: top products by `revenueCents DESC`, then `productId ASC`; categories by `revenueCents DESC`, then category alphabetically. No rows => numeric zero and an empty `items` array. `changePercent` must be `null` if previous revenue is zero; otherwise round to two decimal places. Responses should not include DB passwords, connection strings or stack traces.

Implement services and repository ports with Spring Data/JPA or parameterized JDBC/JPQL aggregates **without raw user-supplied SQL**. Controllers adapt DTOs; business logic does not depend on web or persistence packages. No login is necessary for this local synthetic dataset, but only expose the UI and backend to the laptop by port-forward for the demo.

## Frontend acceptance scope

Angular standalone component(s), read-only, one page. Show:
- Title `Retail Sales Insights`, selected date range default `2026-11-16` to `2026-11-22`.
- Three KPI cards: revenue in EUR formatted from cents, sales count and units sold.
- Top five products and category breakdown as two simple responsive HTML tables.
- A comparison card against `2026-11-09` to `2026-11-15`.
- Loading, empty-data and error states (including backend unreachable).
- A date-range control that refreshes queries. For comparison, derive previous period by shifting the selected inclusive range by its full length.
- No charting library, no authentication screen, no LLM in the frontend.

Use Angular HttpClient and relative paths `/api/insights/...` exclusively so the frontend Nginx proxy calls the Spring Service. A browser at `http://localhost:18090` should work without CORS configuration.

## Tests / acceptance criteria

- **AC-01**: Calling existing MCP tools creates one small ephemeral environment, Spring repo and Angular repo; each appears in the platform catalog.
- **AC-02**: Flyway migrations run once against the platform PostgreSQL and seed the fixed dataset; count matches `sales.csv` (see dataset README).
- **AC-03**: Each REST operation returns the documented keys, validated date parameters and deterministic values matching SQL aggregates; unknown/untrusted input cannot become SQL.
- **AC-04**: `./mvnw verify` passes with unit tests, controller tests, PostgreSQL Testcontainers integration tests and ArchUnit rules; Gitea quality pipeline succeeds.
- **AC-05**: `npm run lint && npm test && npm run build` passes; mock HttpClient tests cover happy path, loading and failures.
- **AC-06**: Argo CD reconciles backend and frontend and the portal reports Ready.
- **AC-07**: `kubectl -n env-retail-demo port-forward svc/retail-sales-web 18090:80` serves the UI; `kubectl -n env-retail-demo port-forward svc/retail-sales-insights 18080:80` serves the API.
- **AC-08**: Both frontend and API are accessed only via local port-forward; no LoadBalancer, external ingress or direct DB access is required.

## Demonstration commands

```bash
kubectl -n env-retail-demo get springservices,apps,postgresdatabases,pods
kubectl -n env-retail-demo port-forward svc/retail-sales-web 18090:80
# separate terminal:
kubectl -n env-retail-demo port-forward svc/retail-sales-insights 18080:80
curl -fsS 'http://127.0.0.1:18080/api/insights/summary?from=2026-11-16&to=2026-11-22'
# browser: http://127.0.0.1:18090
```

## Out of scope

No autonomous SQL generation, real customer sales, streaming ingestion, shopping cart, admin CRUD, payment operations, BI engine, GraphRAG, multiple tenants or internet exposure. Once AC-01..AC-08 pass, continue with [Spec 02](retail-sales-insights-02-zero-ui.md).
