---
name: api-to-mcp
description: Use when someone wants an existing REST business API to be queryable from Claude Code or another MCP client, using a remote Kubernetes MCP endpoint.
---

# API-to-MCP Golden Path — private remote deployment

1. Confirm the existing SpringService and ephemeral environment are ready. **Do not** create a second database or another backend.
2. Discover platform capabilities and the current approved OpenAPI GET operations.
3. Call `create_api_mcp_adapter(name, description, team, backend_service, environment)`.
   It generates a repo with Python Streamable HTTP MCP runtime, tests,
   multiarch Gitea pipeline, and Kubernetes Deployment/ClusterIP Service.
4. Clone the generated Gitea repository. Replace the sample `operations.json`
   with **reviewed** read-only GET operations matching the backend API.
   For Retail, the Starter Kit provides
   `examples/scenarios/example/data/retail-operations.json`.
5. Run tests, commit and push. Check the pipeline, Argo CD and deployment
   readiness in the same `env-<environment>` namespace.
6. For EACH consumer, use their **own** authorized Kubernetes context to
   start `kubectl -n env-<environment> port-forward svc/<adapter> 18081:8080`.
   Every laptop has its own localhost; never share credentials.
7. Register HTTP MCP globally within the individual's Claude Code user profile
   from ANY directory:
   `claude mcp add --scope user --transport http <adapter> http://127.0.0.1:18081/mcp`.
   Use `claude mcp list` and `/mcp` to verify and ask business questions.
8. Explain limitations: this private remote demo uses Kubernetes authorization
   for the port-forward, **not agent OAuth identity delegation** or a public
   MCP gateway. Only approved GET tools are available. Reject write requests,
   arbitrary SQL and unsupported URLs.

The same generated code supports local stdio for debugging, but the main
Zero-UI demo uses the remote Kubernetes server. Do not prescribe these
technical steps inside a business specification.
