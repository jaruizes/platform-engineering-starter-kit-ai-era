# Platform API

The channel-independent core of the platform. The portal, the
[platform MCP server](../../access/mcp) and [`platformctl`](../../access/cli)
are channels: they send what a person or an agent asked for, with their
token, and the API authenticates, authorizes and does it. Without a portal,
nothing is lost.

| Operation | What it does |
|---|---|
| `GET /v1/me` | Who the token says you are: person, agent, autonomous agent, teams |
| `GET /v1/offering` | Golden Paths and capabilities, with parameters and guardrails (for agents) |
| `GET /v1/golden-paths` | Code Golden Paths and their parameters |
| `POST /v1/golden-paths/{name}/repositories` | Runs a code Golden Path: checks the parameters, renders `skeleton/` and creates the repository |
| `POST /v1/capability-proposals` | Validates a `CapabilityDefinition` and opens its pull request. Only people in platform-team |
| `GET`, `POST /v1/environments`, `GET`, `DELETE /v1/environments/{name}` | Ephemeral environments |
| `POST /v1/environments/{name}/services` | Deploys an image with the SpringService runtime Golden Path |
| `GET /v1/environments/{env}/services/{name}/status` | Delivery of a service: pipeline, Argo CD and pods |
| `GET /v1/services/{name}/quality` | Commit-linked quality evidence |
| `POST /v1/capabilities/{capability}/requests`, `GET .../requests/{name}` | Capabilities such as PostgresDatabase |
| `GET /v1/approvals/{id}` | Status of an approval request |

## Identity and authorization

Every request carries a Keycloak access token (`Authorization: Bearer`). The
API checks its signature, issuer, audience (`platform`) and expiry
([`identity.py`](platform_api/identity.py)) and builds the identity: a person,
an agent acting for a person (the agent is the OAuth client, `azp`), or an
autonomous agent of one owner team (client credentials).

Then [`authorization.py`](platform_api/authorization.py) decides, for every
operation, read or write:

| Rule | Decision |
|---|---|
| Team scope | Create, deploy and delete only for your teams; an agent has exactly its person's teams. Reads return only your teams' resources; platform-team reads everything. An autonomous agent only its owner team |
| Delete | Agents only delete what an agent requested for the same person (or the same autonomous agent) |
| Proposals | Only people in platform-team propose capabilities; agents never |
| Agent guardrails | Enforced by Kyverno (small environments, `env-*` only); an agent's request outside them becomes an approval request |

Every decision, allowed or denied, is an event in the audit trail, with the
agent and the person it acted for.

In Kubernetes the API acts **as itself** for people and **as the agents'
identity** (the `platform-mcp` service account, by impersonation) for agents,
so Kyverno applies the agent guardrails as a second line. It writes who the
request is for in annotations that only it may set: `agent`, `on-behalf-of`,
`requester-teams` and `agent-chain`; Kyverno's `team-membership` checks the
team again. Before a delete it records `deleted-by`, `deleted-on-behalf-of`
and `deleter-teams`, so Kyverno can check deletes too.

Until the portal signs people in with Keycloak (increment B of
[identity and access](../../../docs/identity-and-access.md)), it may call with
the channel token `PLATFORM_API_TOKEN` and state the signed-in person and
their catalog teams (`X-Platform-Requester`, `X-Platform-Teams`). That path
never identifies an agent.

## Code Golden Paths

Each Golden Path in [`../golden-paths/<name>/`](../golden-paths) has a
`golden-path.yaml`, the channel-neutral definition:

- `parameters`: name, required, pattern, default and type. `team`,
  `environment` and `spring-service` are checked against the cluster; the
  owner team and the environment must be the requester's.
- `values`: what the skeleton receives, as `${{ }}` expressions over the
  parameters and the requester.
- `skeleton`, `copyWithoutTemplating` and `repository` (name and description).

The skeletons keep their `${{ values.x }}` syntax; the API renders them with a
sandboxed Jinja2 environment. The Backstage `template.yaml` next to it is only
the form. To render a skeleton locally without a cluster:

```bash
PYTHONPATH=platform/capabilities/api python3 -m platform_api.render spring-service /tmp/out \
  name=loyalty-points module=points
```

## The console

The same image runs the platform console (`platform-console`): dashboard,
metrics and human approvals, with the `platform-console` identity. Approvals
by role and with four eyes move into the API with increment B.

## Run and test

```bash
pip install -e 'platform/capabilities/api[test]'
pytest platform/capabilities/api/tests      # also part of make test
```

`make up` builds the image and deploys it ([`deploy/`](deploy)) on port 8083.
Settings: `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE` for Keycloak;
`GIT_API_URL`, `GIT_URL`, `GIT_USERNAME`, `GIT_PASSWORD` for the Git server.
