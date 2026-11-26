# API-to-MCP Golden Path

A **reusable** Backstage Scaffolder template and platform MCP tool
(`create_api_mcp_adapter`) that generates a *separate* Python MCP adapter
repository for an already deployed REST backend.

## Why this pattern?

Humans use an application through Angular; an AI agent uses approved business
capabilities of that **same** application through MCP. The tool adapter uses
HTTP GET to the existing Spring service, not direct JDBC or arbitrary SQL.

```text
Claude Code (natural language)
  -> MCP stdio (generated Python adapter)
     -> fixed allowlisted REST operation over localhost:18080
        -> kubectl port-forward -> SpringService:80 -> PostgreSQL
```

The generated `operations.json` declares names, descriptions, fixed `/api/`
paths and typed query parameter allowlists. It must be reviewed and customized
based on the service's OpenAPI contract. Two stable MCP tools:
`list_api_operations` and `query_api_operation`.

## How to generate

From Claude Code configured with platform MCP, ask:

> Create an MCP adapter named retail-sales-mcp for the already deployed
> retail-sales-insights backend in the retail-demo environment, owned by
> platform-team.

Or choose **Create → API to MCP adapter (Zero-UI)** in Backstage.

The platform MCP tool checks the environment and deployed SpringService,
runs the same Backstage template, and returns a Git clone URL. It does *not*
deploy an MCP pod: generated adapter is local stdio. The generated README
shows how to port-forward the backend and register Claude Code.

## Demo

1. Complete [Retail Spec 01](../../../../examples/scenarios/example/specs/retail-sales-insights-01-app.md).
2. Complete [Retail Spec 02](../../../../examples/scenarios/example/specs/retail-sales-insights-02-zero-ui.md).
3. Copy the reviewed [Retail operation allowlist](../../../../examples/scenarios/example/data/retail-operations.json)
   to `operations.json` of the generated adapter repo.
4. Run its pytest suite and register with Claude Code.

## Controls and limitations

GET-only, explicit fixed-path allowlisting, strict parameter names/types,
response size bound, localhost-only plaintext HTTP; remote endpoints require
HTTPS. The backend validates values and enforces business authorization.
Local stdio does **not** provide agent-specific identities, delegated OAuth,
fine-grained production audit or gateway-managed token accounting.

The Golden Path is not automatic OpenAPI code generation: the agent takes the
OpenAPI contract as input and explicitly maps its approved operations to the
versioned adapter `operations.json`, with review.
