# Golden Path demo troubleshooting and template corrections

These fixes apply to `feat/zeroui-use-case` and **newly generated repositories**.
A Scaffolder template is copied once at repository creation: modifying the
Starter Kit does **not** rewrite an existing `retail-sales-web` or
`retail-sales-mcp` repository in Gitea.

## Angular 20.3: tests, Sonar, and publishing

The Angular Golden Path now has:

- `angular.json`: `codeCoverage` and `codeCoverageReporters` for the
  Angular 20.3 unit-test builder; the test script no longer passes the unsupported
  CLI `--coverage` flag.
- `tools/normalize-lcov.mjs`: converts Vitest `dist/test-out/<run>/src/...`
  records to repository paths `src/...` **only when the source file exists**.
  The script runs after `ng test`, produces `coverage/lcov.info`, and fails
  if no legitimate LCOV records exist.
- `sonar-project.properties`: separates `*.spec.ts` from production sources
  and tells Sonar where to find the corrected LCOV file.
- `.gitea/workflows/deliver.yaml`: uses actual `crane append` flags
  `--new_layer`/`--new_tag`; creates amd64 and arm64 variants and an index
  under the final image tag before GitOps.

To bring these corrections into an **already generated Angular repo**, review
and port the modifications to the files listed above. Do not overwrite
application-specific tests, source code, environment values or unrelated
changes. Confirm locally:

```bash
npm install
npm run test:lcov
npm test
npm run lint
npm run build
```

On Gitea CI, confirm the Sonar report recognizes coverage and that the
published image has both `linux/amd64` and `linux/arm64` entries:

```bash
crane manifest <registry/image:tag>
```

A multi-architecture publication needs credentials allowing all three tags
(the two architecture-specific intermediates and the final index). Do not
bypass or relax Sonar's quality gate to hide missing coverage.

## MCP API adapter: retail queries and meaningful errors

- `rest_mcp_adapter/bridge.py` now validates operation names separately from
  query parameter names; `previousFrom` and `previousTo` are valid
  camelCase query parameters.
- `rest_mcp_adapter/server.py` raises the MCP v2 `ToolError` for safe,
  known validation and transport errors so Claude Code gets an actionable
  explanation rather than a generic tool failure.
- The adapter now has tests that load the actual retail allowlist and verify
  the error messages.

For an older `retail-sales-mcp` repository configured for **local stdio**,
port these two Python files and run `pytest -q`. For the recommended
**remote Kubernetes** deployment, migrate the new Streamable HTTP runtime,
`deploy/mcp.yaml`, image pipeline and generated README (or create a new
adapter repository from the updated Golden Path).

## Spring coverage: what CI does *not* exercise

The Spring Golden Path's Gitea pipeline deliberately uses
`./mvnw verify -DskipITs`, because its current runner does not offer a
Docker daemon for Testcontainers. **Integration tests and their code
coverage do not contribute to Sonar's CI coverage.** For JPA/persistence
adapters, add focused isolated unit tests and also run `./mvnw verify`
locally with Docker. The generated `AGENTS.md` makes this limitation
explicit; Sonar gates remain blocking.

A later platform improvement should enable an isolated integration-test
executor instead of trying to share the host Docker socket with
untrusted pipeline code.

## Platform validation

```bash
make test
# The normalizer has an independent Node built-in test:
node --test platform/capabilities/golden-paths/angular-app/skeleton/tools/normalize-lcov.test.mjs
```

Actual Gitea pipelines, multi-arch ECR publication, Angular unit tests of a
generated app, and Claude Code MCP restart require the **running demo
platform** and cannot be inferred merely from static template checks.

## Remote MCP delivery and access (new default)

The updated Golden Path now deploys a private Streamable HTTP MCP in the
backend's namespace instead of requiring a local stdio runtime. The Gitea
pipeline builds its Python image for amd64/arm64; the platform runner needs
`python3-pip` and `python3-venv` (redeploy the runner image). Argo CD's
`services` AppProject now allows the generated namespaced Deployment/Service.

If the original `retail-sales-mcp` repository was already scaffolded before
this enhancement, it **will not** receive these changes automatically. Create
an adapter repository with a new name (preferred for a clean demo), or port
its runtime, deploy/mcp.yaml, pipeline, build script, and documentation.

For remote access, port-forward `svc/retail-sales-mcp 18081:8080` and add
`claude mcp add --scope user --transport http retail-sales http://127.0.0.1:18081/mcp`.
Every attendee needs an independent port-forward and their own Kubernetes
identity; the resulting MCP registration is global to their Claude Code user
profile, not to the folder containing the app code.
