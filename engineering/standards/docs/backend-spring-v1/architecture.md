# Backend architecture v1: layered Spring (deprecated)

## Purpose

Backend Spring v1 is the classic layered Spring Boot architecture (controller → service → repository) used by older services; it is **deprecated** for new services, which must use Backend Spring v2 (hexagonal).

This document describes how v1 services are structured so they can be maintained safely and migrated to v2 incrementally. The verifiable rules are in `architecture-rules.md` (BL-001 to BL-015). Shared engineering rules (development rules, technology policy, testing strategy) live in `engineering/standards/docs/common/` and apply to v1 as well; they are not repeated here.

---

# Status at a Glance

```text
Version       Backend Spring v1 (layered)
Status        DEPRECATED — maintenance only
New services  Not allowed (use Backend Spring v2)
Changes       Bug fixes, security fixes, small features
Replacement   Backend Spring v2 (hexagonal, module-first)
```

---

# Architectural Goals

v1 was designed for simple CRUD-oriented services. Its goals were:

- Keep a predictable structure that any Spring developer can read on day one.
- Separate HTTP handling, business logic and data access into distinct layers.
- Keep dependencies flowing in one direction: controllers → services → repositories.
- Never expose JPA entities through the REST API.
- Keep the database schema versioned and reproducible.
- Make the layering checkable automatically with ArchUnit.

v1 deliberately accepts one trade-off that v2 does not: **JPA entities are the domain model**. This is the main reason it is deprecated. Business rules end up coupled to persistence mapping, and the model becomes hard to change as the service grows.

---

# Package Structure

v1 services are organized **by layer** first. A single root package holds one package per layer:

```text
com.example.orders/
├── OrdersApplication.java
├── controller/        REST controllers (@RestController)
├── service/           business logic (@Service, @Transactional)
├── repository/        Spring Data JPA repositories
├── model/             JPA entities (@Entity), enums, value types
├── dto/               request/response DTOs and mappers
├── exception/         business exceptions and @ControllerAdvice
└── config/            @Configuration classes and properties
```

Resources:

```text
src/main/resources/
├── application.yml
└── db/migration/      Flyway scripts (V1__init.sql, V2__add_status.sql, ...)
```

Large v1 services may add one level of sub-packages per functional area inside a layer (`service/billing`, `service/shipping`). This is allowed but does not turn the service into a module-first structure; the layer remains the first boundary.

---

# Responsibilities per Layer

## Controller

- Receives HTTP requests, validates input with Bean Validation (`@Valid`).
- Maps request DTOs to service calls and service results to response DTOs.
- Chooses HTTP status codes and headers.
- Contains **no business logic** and **never calls repositories**.

## Service

- Owns business rules and use-case orchestration.
- Defines transaction boundaries with `@Transactional`.
- Calls repositories and other services.
- Works with entities and DTOs, but must not depend on controllers or on HTTP types (`HttpServletRequest`, `ResponseEntity`).

## Repository

- Spring Data JPA interfaces extending `JpaRepository` or `CrudRepository`.
- Derived queries and `@Query` (JPQL) are the default.
- No business logic. Custom implementations are allowed only for queries that Spring Data cannot express.

## Model

- JPA entities, embeddables and enums.
- May contain simple invariants that protect the entity's own state (for example, a `cancel()` method that checks status).
- Must not depend on DTOs, services or controllers.

## DTO

- Request and response records exposed by the REST API.
- Mappers between DTOs and entities: MapStruct interfaces or small hand-written mapper classes.
- DTOs carry Bean Validation annotations; entities do not depend on DTOs.

## Config

- `@Configuration` classes, `@ConfigurationProperties` records, security configuration, HTTP client beans.
- No business logic.

---

# REST and API Conventions

- v1 services expose **synchronous REST only**. Messaging (Kafka or other brokers) is not part of v1; a service that needs it should be migrated to v2 first or justified with an ADR.
- Resources use plural nouns and stable paths: `/api/v1/orders`, `/api/v1/orders/{id}`.
- Request and response bodies are DTOs. Entities are never serialized directly.
- Input is validated with Bean Validation on DTOs (`@NotNull`, `@Size`, `@Positive`) and `@Valid` on controller parameters.
- Errors are returned as RFC 9457 Problem Details (`application/problem+json`).
- Externally exposed APIs are described with OpenAPI (springdoc or a contract-first file).
- Pagination uses `page`, `size` and `sort` parameters and returns a page DTO, not Spring's `Page` serialized as-is.
- API versioning is by path prefix (`/api/v1`). Breaking changes require a new version.

---

# Persistence

- PostgreSQL is the database.
- Spring Data JPA / Hibernate is the access layer.
- Flyway owns the schema. `spring.jpa.hibernate.ddl-auto` must be `validate` or `none` outside local throwaway profiles; never `update` or `create`.
- Migration scripts are immutable once released; fixes go in a new script.
- Entities use explicit table and column names when they differ from the defaults.
- Associations default to `LAZY`. Fetch joins or entity graphs are used where a use case needs related data, to avoid N+1 queries.
- Native SQL, `JdbcTemplate` and `JdbcClient` are exceptions that need a short justification in the code review.
- A v1 service owns its tables. It must not read or write another service's schema.

---

# Error Handling

- Business errors are expressed as specific exceptions in `exception/` (for example `OrderNotFoundException`, `InvalidOrderStateException`).
- A single global `@RestControllerAdvice` translates exceptions into Problem Details:
  - not found → `404`;
  - business rule violation → `409` or `422`;
  - validation failure (`MethodArgumentNotValidException`) → `400` with field errors;
  - anything unexpected → `500` with a generic message.
- Controllers do not catch exceptions to build error responses themselves.
- Stack traces, SQL and internal class names are never returned to clients. They are logged with the correlation id.

---

# Transactions

- Transactions start and end in the **service layer**.
- Write methods use `@Transactional`; read methods use `@Transactional(readOnly = true)`.
- Controllers and repositories do not declare their own transactions (Spring Data's defaults on repository methods are fine).
- Remote HTTP calls inside a transaction should be avoided. When unavoidable, they need bounded timeouts and the code must handle the call failing after the database write.
- Open Session in View is disabled (`spring.jpa.open-in-view=false`), so lazy loading outside a transaction fails fast instead of issuing hidden queries.

---

# Configuration

- Configuration lives in `application.yml` plus profile files. Environment-specific values come from environment variables or the platform's secret store.
- Typed `@ConfigurationProperties` records are preferred over scattered `@Value` fields.
- Secrets are never committed, including in test profiles.
- Outbound HTTP clients (`RestClient`, `WebClient` or `RestTemplate` on older services) are created as beans in `config/` with explicit connect and read timeouts.

---

# Testing

v1 follows the shared testing strategy in `common/testing.md`. Layer-specific guidance:

| Level | Tooling | Scope |
|---|---|---|
| Unit | JUnit 5 + Mockito | Services with mocked repositories; mappers; entity invariants |
| Web slice | `@WebMvcTest` + MockMvc | Controllers, validation, error mapping |
| Persistence slice | `@DataJpaTest` + Testcontainers PostgreSQL | Custom queries, mappings, Flyway scripts |
| Integration | `@SpringBootTest` + Testcontainers | Main flows end to end through HTTP |
| Architecture | ArchUnit | Layer dependencies, no cycles, package placement |

`@DataJpaTest` runs against a real PostgreSQL container with Flyway enabled (`@AutoConfigureTestDatabase(replace = NONE)`), not against H2.

The ArchUnit test uses `layeredArchitecture()` with these layers:

```text
Controller  → may access Service, Dto (entities only as values passed to mappers)
Service     → may access Repository, Model, Dto
Repository  → may access Model
Nothing     → may access Controller
```

plus a `slices().should().beFreeOfCycles()` rule. These tests run in `./mvnw verify` locally and in CI.

---

# Observability

- Logs are structured (JSON) and include the trace and correlation ids.
- Spring Boot Actuator exposes `health`, `info` and `prometheus` endpoints; other endpoints stay disabled or protected.
- OpenTelemetry (agent or Micrometer Tracing bridge) is used for traces where the service is part of a traced flow.
- Business-significant failures are logged once, at the error handler or at the service boundary, not at every layer.

---

# Status and Migration to v2

## Status

v1 is **deprecated**:

- **No new services** may be created on v1. New services start from the Spring service template, which implements v2.
- **Maintenance is allowed**: bug fixes, security fixes, dependency upgrades and small features that fit the existing layers.
- **Large new features** in a v1 service are a trigger to migrate the affected area to v2 first.
- v1 services must still pass their ArchUnit layered tests and the rules in `architecture-rules.md`.

## Migrating Incrementally (Strangler by Functional Module)

Migration is done **one functional module at a time**, not with a big-bang rewrite. The service keeps running and shipping during the migration.

1. **Choose a module.** Pick a cohesive functional area (for example `billing`) with clear tables and endpoints. Prefer the area with the most upcoming change.
2. **Record the decision.** Write a short ADR naming the module, the target v2 structure and the end state of the migration.
3. **Create the v2 module.** Add `com.example.orders.billing/{domain,business,infrastructure}` alongside the existing layered packages. Add the v2 ArchUnit rules scoped to that module.
4. **Extract the domain.** Move business rules out of entities and services into plain domain types. Create new JPA entities under `billing/infrastructure/persistence` mapped to the **same tables**; no schema change is needed at this step.
5. **Move the endpoints.** Re-implement the module's controllers as REST adapters in `billing/infrastructure/rest`, keeping the same paths and contracts. Contract tests protect existing clients.
6. **Redirect callers.** Other layered services that used the old billing service call the new module through its published port, not its repositories.
7. **Delete the old code.** Remove the module's classes from `controller/`, `service/`, `repository/`, `model/` and `dto/`. Narrow the v1 ArchUnit rules so they no longer cover the migrated module.
8. **Repeat** until no layered packages remain, then remove the v1 rules and mark the service as v2.

During migration, the v1 layered packages and the v2 modules coexist, each checked by its own ArchUnit rules. The v2 module must not depend on the layered packages; layered code may call the v2 module only through its ports.

## What Not To Do

- **Do not half-mix hexagonal packages into a layered service without an ADR.** Adding a `domain/` or `ports/` folder inside `service/` "to start the migration" creates a third, undocumented architecture that neither rule set checks.
- Do not migrate by layer (for example, "all repositories first"). Migration is by functional module.
- Do not share JPA entities between a migrated v2 module and the remaining layered code.
- Do not change the public API while moving a module. Contract changes are separate work.
- Do not start a new v1 service "because it is faster". The template produces v2 with the same effort.
