# ${{ values.name }}: instructions for AI agents

${{ values.description }}

This service was created from the platform's **Spring service** template and
follows the **backend v2 (hexagonal Spring)** architecture
(`platform.starterkit.dev/architecture: backend-spring-v2` in
`catalog-info.yaml`). Other services may follow other architectures or
versions: use the rules of this one. The rules below are the essentials; the
full documents are the source of truth.

## Where the standards are

- Portal MCP server (`portal` in `.mcp.json` of the platform repository):
  `platform.get-standards-for-entity` with `component:default/${{ values.name }}`
  returns the documents that apply, in order; read them with
  `platform.get-engineering-standard` (for example
  `backend-spring-v2/architecture-rules`). To find a topic, use
  `platform.search-engineering-standards` with `architecture: backend-spring-v2`.
- Portal: http://localhost:7007/docs/default/component/engineering-standards/backend-spring-v2/architecture-rules/

## Structure (architecture rules AAC-001 to AAC-004)

Code is organized by functional module first, then by layer:

```text
${{ values.rootPackage }}
├── Application.java
└── <module>/            (the first one is ${{ values.module }})
    ├── domain/          model/, ports/, exceptions/  plain Java only
    ├── business/        use cases, depends on domain only
    └── infrastructure/  adapters
        ├── api/rest/    controllers, dto/, mapper/
        ├── persistence/ entity/, repository/, adapters implementing domain ports
        ├── messaging/
        └── client/
```

- Dependencies go `infrastructure → business → domain`, never the other way.
- `domain` has no Spring, JPA, HTTP, Kafka, Jackson or provider SDK types.
- A module never reads another module's tables or JPA entities; it uses a
  port, API or event.
- A new functional module is a new package next to `${{ values.module }}`, with
  the same three layers. It is not a new service.

## Technology (technology policy)

Maven, Spring Boot, Spring Data JPA with Flyway migrations, PostgreSQL,
OpenAPI for the external API (`contracts/openapi.yaml`), JUnit 5, AssertJ,
Testcontainers and ArchUnit. Do not add Kafka, Redis, another database or any
technology outside the policy without an approved ADR. Do not add a
dependency for something the stack already does.

## Implementation (development rules)

- The simplest correct implementation; no speculative abstractions.
- Use the domain language for names.
- `BigDecimal` for money and precision-sensitive values.
- Errors are explicit; external errors never expose stack traces, SQL or
  provider details.
- Configuration comes from the environment; never commit secrets.
- No unrelated refactoring in a feature change.

## Delivery (pipeline and GitOps)

A push to `main` is a deployment. The platform pipeline
(`.gitea/workflows/deliver.yaml`) runs the unit tests and architecture rules,
builds the image with Jib and writes it into `deploy/app.yaml`; Argo CD then
applies `deploy/` to the environment. You do not build images, call
`kubectl apply` or deploy by hand.

- `deploy/app.yaml`: how the service runs (new-service Golden Path). Leave
  `spec.image` to the pipeline.
- `deploy/database.yaml`: its PostgreSQL (postgres-database capability). The
  connection reaches the service as `SPRING_DATASOURCE_*` variables.
- Follow a deployment with the platform MCP server: `get_service_status`
  says whether the pipeline, Argo CD and the service are done, and shows the
  logs when the service does not start.
- Try it from a laptop with `kubectl -n env-<environment> port-forward
  svc/${{ values.name }} 8080:80` and `curl http://localhost:8080/...`.

## Before you finish

Run `./mvnw verify`. It runs the unit tests, the architecture rules in
`src/test/java/**/architecture/ArchitectureTest.java` and the integration
tests (Testcontainers needs Docker). The pipeline runs the same command,
without the integration tests. Then commit and push to `main` to deploy.

Never weaken, skip or delete an architecture rule to make a change pass. If
a rule cannot be met, stop and tell the user: the options are to change the
implementation or to approve an ADR.
