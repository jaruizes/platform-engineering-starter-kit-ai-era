# API-to-MCP Golden Path — Remote, private Zero-UI

The platform exposes `create_api_mcp_adapter` via MCP and the Backstage
`api-mcp-adapter` Software Template. It generates an independent Python
repository that wraps an **existing REST business API** as MCP tools.

**Default output:** a real remote Streamable HTTP MCP server, **deployed into
the same ephemeral environment** as its Spring backend, using Gitea Actions,
the shared image registry and Argo CD. It is ClusterIP-only, with **no Ingress
and no public endpoint**.

```text
Claude Code (any working directory, any authorized laptop)
    |  http://127.0.0.1:18081/mcp
kubectl port-forward svc/retail-sales-mcp 18081:8080
    |  Kubernetes API, authenticated per attendee
env-retail-demo / ClusterIP retail-sales-mcp:8080
    |  HTTP internal, reviewed GET operations
env-retail-demo / retail-sales-insights:80
    |  original business logic
PostgreSQL
```

The generated `operations.json` is an explicit **GET-only allowlist** with
names, descriptions and typed parameters. The MCP exposes
`list_api_operations` and `query_api_operation`; the Spring backend keeps
data access and authorization. No dynamic SQL or direct DB credentials.

## Golden Path flow

1. Deploy the Spring REST app first and verify its contract.
2. Ask Claude Code (connected to the platform MCP) to create the
   `retail-sales-mcp` adapter for `retail-sales-insights` in `retail-demo`,
   owned by `platform-team`. The platform checks the environment and
   backend, and runs the Backstage Scaffolder template.
3. Clone the Gitea repo. Replace its sample `operations.json` with reviewed
   GET operations from the backend API (for Retail use
   [retail-operations.json](../../../../examples/scenarios/example/data/retail-operations.json)).
4. Run its `pytest` checks and push to main. The generated Gitea pipeline
   builds amd64 and arm64 OCI images **without Docker daemon**, updates
   `deploy/mcp.yaml`, and Argo CD reconciles a Deployment and ClusterIP
   Service in `env-retail-demo`.
5. Check `kubectl -n env-retail-demo get deployment,svc` and
   `kubectl -n env-retail-demo rollout status deployment/retail-sales-mcp`.
6. Each participant configures their own **port-forward**, then registers
   the private remote HTTP URL in Claude Code with **user scope**, independent
   of their current directory:

   ```bash
   kubectl -n env-retail-demo port-forward svc/retail-sales-mcp 18081:8080
   # Other terminal, from ANY directory:
   claude mcp add --scope user --transport http retail-sales http://127.0.0.1:18081/mcp
   claude mcp list
   claude
   ```

## Attendee access

There is ONE MCP Deployment, shared by authorized participants. Each laptop's
`localhost` is different: every participant needs their **own** `kubectl
port-forward`. Before the event, grant the participant read/port-forward
access to the specific service and pods in `env-retail-demo` via their OWN
kubeconfig/AWS identity. Never share your AWS session, kubeconfig or long-lived
credential. A participant who cannot reach the EKS Kubernetes API cannot use
the port-forward; a secured public/private HTTPS MCP gateway would be a
future alternative.

Claude Code `--scope user` makes the MCP discoverable in other directories.
If the local name `retail-sales` already exists, first remove/reconfigure
it (for example `claude mcp remove --scope user retail-sales`).

## Rebuilding the platform

The feature changes the shared Gitea Actions runner to include pip and Python
venv for the daemonless build. Redeploy/update the platform runner and reapply
`platform/capabilities/delivery/argocd/services.yaml` before using a newly
generated adapter. The installer will apply the latter when rerun.

**Existing Gitea adapter repositories are NOT updated automatically** by
changes to the Golden Path. Either create a new adapter repository or migrate
its code, GitOps manifests and CI using the generated source as reference.

## Boundaries

The MCP process also supports `stdio` for debugging, but the **remote mode is
the default demo**. It uses Streamable HTTP, stateless JSON responses and one
replica; probes use TCP. The server is not exposed by a LoadBalancer or Ingress.

Kubernetes RBAC and port-forward govern who can access the demo endpoint, but
the MCP **does not authenticate agent identities individually**. In-cluster
workloads may also reach a ClusterIP service unless additional NetworkPolicies
are installed. Enterprise use requires authenticated MCP gateway, agent-specific
authorization, network segmentation, rate limits and tool-level audit.
