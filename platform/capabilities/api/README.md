# Platform API

The channel-independent core of the platform for the capabilities that used to
live in Backstage. The portal, the [platform MCP server](../../access/mcp) and
[`platformctl`](../../access/cli) are channels: they send what a person or an
agent asked for, and the API does it. Without a portal, nothing is lost.

| Operation | What it does |
|---|---|
| `GET /v1/golden-paths` | Lists the code Golden Paths and their parameters |
| `POST /v1/golden-paths/{name}/repositories` | Runs a code Golden Path: checks the parameters (team, environment, backend service), renders `skeleton/` and creates the repository in the Git server with a first commit |
| `POST /v1/capability-proposals` | Validates a `CapabilityDefinition` against the [schema](../schema/capability-definition.schema.json) and opens the pull request with `platform/capabilities/infrastructure/<name>/capability.yaml`. Only people can propose; agents get `403` |
| `GET /healthz` | Liveness |

Every request states its requester (`user:default/<name>` or `agent:<name>`).
The API writes it into the repository (`requestedBy`, `Requested-by:` in the
commit) and into the audit trail, as Kubernetes events from `platform-api` with
the `requester-type` annotation that the console and the portal already show.

## Code Golden Paths

Each Golden Path in [`../golden-paths/<name>/`](../golden-paths) has a
`golden-path.yaml`, the channel-neutral definition:

- `parameters`: name, required, pattern, default and type. `team`,
  `environment` and `spring-service` are checked against the cluster.
- `values`: what the skeleton receives, as `${{ }}` expressions over the
  parameters and the requester.
- `skeleton`, `copyWithoutTemplating` and `repository` (name and description).

The skeletons keep their `${{ values.x }}` syntax; the API renders them with a
sandboxed Jinja2 environment. The Backstage `template.yaml` next to it is only
the form; its single step, `platform:golden-path:create`, sends the parameters
here.

To render a skeleton locally without a cluster:

```bash
PYTHONPATH=platform/capabilities/api python3 -m platform_api.render spring-service /tmp/out \
  name=loyalty-points module=points
```

## Authentication

Until people and agents have their own identity (increment A of
[identity and access](../../../docs/identity-and-access.md)), channels call the
API with a shared bearer token, `PLATFORM_API_TOKEN` (secret
`platform-api-token` in `platform-system`), and state the requester.

## Run and test

```bash
pip install -e 'platform/capabilities/api[test]'
pytest platform/capabilities/api/tests      # also part of make test
```

`make up` builds the image and deploys it ([`deploy/10-platform-api.yaml`](deploy/10-platform-api.yaml))
on port 8083. The API reads `GIT_API_URL`, `GIT_URL`, `GIT_OWNER`,
`GIT_USERNAME`, `GIT_PASSWORD` for the Git server (Gitea today).
