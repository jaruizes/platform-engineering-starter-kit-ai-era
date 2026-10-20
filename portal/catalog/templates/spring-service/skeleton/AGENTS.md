# ${{ values.name }}: instructions for AI agents

${{ values.description }}

This service was created from the platform's **Spring service** template and
must follow the organization's engineering standards. The rules below are the
essentials; the full documents are the source of truth.

## Where the standards are

- Portal MCP server (`portal` in `.mcp.json` of the platform repository):
  `platform.list-engineering-standards` and `platform.get-engineering-standard`
  return the documents. Read the relevant one before a design decision.
- Portal: http://localhost:7007/docs/default/component/engineering-standards

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

## Before you finish

Run `./mvnw verify`. It runs the unit tests, the architecture rules in
`src/test/java/**/architecture/ArchitectureTest.java` and the integration
tests (Testcontainers needs Docker). CI runs the same command.

Never weaken, skip or delete an architecture rule to make a change pass. If
a rule cannot be met, stop and tell the user: the options are to change the
implementation or to approve an ADR.
