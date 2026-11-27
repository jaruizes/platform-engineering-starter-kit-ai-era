# platformctl

The platform from the terminal, without a portal: a thin channel of the
[platform API](../../capabilities/api), like the portal and the platform MCP
server. Only the Python standard library (and PyYAML to read YAML definitions).

You sign in once with the platform's identity provider (Keycloak, device
flow: it prints a link to open in a browser). The platform API knows who you
are and which teams you are in; you never state it.

```bash
platform/access/cli/platformctl.py login        # marta / demo on make up
platform/access/cli/platformctl.py whoami
platform/access/cli/platformctl.py request-environment checkout pr-123 "Test PR 123"
platform/access/cli/platformctl.py environments
platform/access/cli/platformctl.py create spring-service name=loyalty-points \
  description="Loyalty points" owner=checkout module=points environment=pr-123
platform/access/cli/platformctl.py delete-environment pr-123
platform/access/cli/platformctl.py propose my-capability.yaml   # platform-team only
```

Tokens are kept in `~/.config/platformctl/` (readable only by you) and
refreshed while the session lasts.

**Codex** has no OAuth sign-in of its own for MCP servers: get it a token of
the `codex` client, for you, and Codex sends it as `PLATFORM_TOKEN`
([`.codex/config.toml`](../../ai/agent-tooling/clients/codex/config.toml)):

```bash
platform/access/cli/platformctl.py login --client codex
export PLATFORM_TOKEN="$(platform/access/cli/platformctl.py token --client codex)"
```

| Setting | Default |
|---|---|
| `PLATFORM_API_URL` | `http://localhost:8083` (`make up`); on AWS `https://<host>:8083`, with the demo CA trusted (`SSL_CERT_FILE`) |
| `PLATFORM_ISSUER` | `http://localhost:8180/realms/platform`; on AWS `https://<host>:8180/realms/platform` |
| `PLATFORM_TOKEN` | An access token to use instead of the one from `login` (automation) |
