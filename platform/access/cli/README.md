# platformctl

The platform from the terminal, without a portal: a thin channel of the
[platform API](../../capabilities/api), like the portal and the platform MCP
server. Only the Python standard library (and PyYAML to read YAML definitions).

```bash
export PLATFORM_API_TOKEN="$(kubectl -n platform-system get secret platform-api-token -o jsonpath='{.data.token}' | base64 -d)"
export PLATFORM_USER=user:default/ana     # until sign-in with Keycloak

platform/access/cli/platformctl.py golden-paths
platform/access/cli/platformctl.py create spring-service name=loyalty-points \
  description="Loyalty points" owner=checkout module=points environment=checkout-dev
platform/access/cli/platformctl.py propose my-capability.yaml --name Ana
```

`PLATFORM_API_URL` defaults to `http://localhost:8083` (`make up`). On AWS it is
`https://<host>:8083`, with the demo CA trusted (`SSL_CERT_FILE`).
