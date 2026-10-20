# Developer portal

[Backstage](https://backstage.io) for humans and AI agents, on top of the same Golden Paths.

| Piece | What it does |
|---|---|
| [`catalog/`](catalog) | Sample organization, the platform components, the two MCP servers as APIs, the AI resources (rules and skill) and the Software Templates |
| [`plugins/platform-backend`](plugins/platform-backend) | Brings environments and services from the cluster into the catalog, runs the Golden Paths from the templates on behalf of the signed-in person, serves agent approvals and metrics, and adds read-only context tools for agents (`get-team-usage`, `list-pending-approvals`) |
| [`plugins/platform`](plugins/platform) | The **AI Platform** page (metrics and approvals) and the **Golden Path request** card on environments and services |
| [`app-config.yaml`](app-config.yaml) | Configuration in the local cluster, including the MCP actions server for agents |
| [`deploy/`](deploy) | Identity, permissions and deployment in the cluster |

`make up` at the root of the repository builds it with the [`Dockerfile`](Dockerfile) and deploys it at <http://localhost:7007>.

## Humans act through templates, agents through the platform MCP server

Agents get the portal as a read-only MCP server (`/api/mcp-actions/v1/context`): catalog, Kubernetes status, search, team usage and pending approvals. The Software Templates are not exposed to agents on purpose, and the template actions refuse to run without a signed-in person. Agents act through the platform MCP server, with their own identity, so the agent guardrails always apply to them.

## Developing

Requires Node.js 22 or 24.

```bash
yarn install
yarn tsc
yarn build:backend
```
