# Logical architecture and code ownership

The source tree follows the [Platform Engineering 2.0 logical architecture](../README.md). Architecture groups express responsibilities, not necessarily separate deployable services.

| Layer | Source | Responsibility |
|---|---|---|
| Access & Experience | `platform/access/portal`, `platform/access/mcp` | Backstage experience and platform/portal MCP contracts |
| Core Engineering | `platform/capabilities` | Golden Paths, infrastructure self-service, quality and delivery |
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
