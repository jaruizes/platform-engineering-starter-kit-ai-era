# Logical architecture and code ownership

The source tree follows the [Platform Engineering 2.0 logical architecture](../README.md). Architecture groups express responsibilities, not necessarily separate deployable services.

| Layer | Source | Responsibility |
|---|---|---|
| Access & Experience | `platform/access/portal`, `platform/access/mcp`, `platform/access/cli`, `platform/access/identity` | Channels: Backstage experience, platform/portal MCP contracts and the `platformctl` CLI, which hold no capability logic; and identity (Keycloak), which tells the platform who people and agents are |
| Core Engineering | `platform/capabilities` | Platform API (`platform/capabilities/api`), Golden Paths, infrastructure self-service, quality and delivery |
| AI & Agent | `platform/ai/agent-tooling` | Agent clients, shared instructions and skills; externally managed agent execution |
| Cognitive & Knowledge | `platform/cognitive/knowledge/standards` | Versioned engineering standards, architecture context and TechDocs |
| Platform Governance | `platform/governance/policies` | Kyverno identity stamping, quotas, agent guardrails and audit constraints |
| Technology integrations | `platform/integrations/crossplane` | Crossplane control plane support |
| Deployment | `deploy/local`, `deploy/aws`, `deploy/install.sh` | k3d and EKS foundation, platform installation |

Ephemeral environments belong to **Infrastructure Self-service**: `platform/capabilities/infrastructure/environments`. PostgreSQL is another infrastructure capability.

**Current implementation vs roadmap:** Backstage, the MCP endpoint, Spring/Angular Golden Paths, ephemeral environments, PostgreSQL, GitOps delivery, Kyverno guardrails and deterministic quality checks have concrete implementations. Agent-specific OAuth identity, managed runtime, model gateway, RAG/GraphRAG, semantic ontology and full AI observability/FinOps are not completed merely because they are represented in the target architecture.

## Ownership and rules

- Place user-facing access adapters in `platform/access`; platform API and MCP contract implementation must not diverge.
- Put capability contract, composition and acceptance examples together under `platform/capabilities`. Shared lifecycle tooling remains in `platform/capabilities/tools`.
- Keep standards as a single knowledge source. Agent skills may reference these standards, not duplicate them.
- Keep organizational policies under governance; capability-specific policies alongside their capability contracts.
- Keep client discovery files at repository root as thin adapters/symlinks into `platform/ai/agent-tooling`.

## Validation

```bash
python3 deploy/check-repository.py
make test
make capability NAME=postgres-database
make up
make demo-quality
make demo-spring-e2e
make down
make aws-up  # requires AWS credentials
make aws-down
```

The refactor should preserve command behavior. Runs requiring Docker, Kubernetes, or AWS must be reported separately from static validation.


## Zero-UI business application consumption

The `api-mcp-adapter` Golden Path lives in `platform/capabilities/golden-paths/api-mcp-adapter/` and is run by the platform API and exposed by the Backstage Software Template, the platform MCP `create_api_mcp_adapter` action and `platformctl`. It generates a Python Streamable HTTP MCP server deployed as a **private Deployment + ClusterIP Service** in the existing backend's ephemeral namespace via Gitea Actions and Argo CD. A per-user port-forward provides access to Claude Code. The server calls only approved GET endpoints through a declarative `operations.json` allowlist; Spring still owns PostgreSQL access and business logic. A local stdio fallback remains available for debugging.

See the [two Retail Sales Insights specs](../examples/scenarios/example/specs/retail-sales-insights-01-app.md) and [fixture](../examples/scenarios/example/data/README.md). Production extensions (service auth, identity delegation, audit, rate limits, managed runtime) remain future architecture capabilities.


### Private remote MCP adapter

The API-to-MCP Golden Path now delivers a **namespaced Deployment and ClusterIP
Service** with Streamable HTTP, using Gitea Actions, a multi-arch OCI image
and Argo CD. The MCP talks only to its declared business REST service inside
the ephemeral namespace. External clients connect through a
**per-person Kubernetes port-forward**, registering an HTTP MCP in Claude Code
at `--scope user`. There is no public Ingress or shared authenticated
MCP gateway yet. The same Python runtime retains stdio for debugging.

The Argo CD `services` AppProject permits Deployment and Service resources
in `env-*` namespaces to deliver this Golden Path. That broadens what a
service repository can deploy: a future platform iteration should enforce
stronger admission controls and owner validation for raw workloads and migrate
to a dedicated Crossplane composite if the capability becomes production-ready.
