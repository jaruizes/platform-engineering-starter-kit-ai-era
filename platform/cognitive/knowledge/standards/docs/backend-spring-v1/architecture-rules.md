# Architecture rules: backend v1 (layered)

## Purpose

These are the verifiable rules that a Backend Spring v1 (layered, deprecated) service must satisfy to be considered architecture-compliant.

This document does not restate the architecture. Structure, rationale and the migration path are in `architecture.md` in this folder. Shared rules in `engineering/standards/docs/common/` (development rules, technology policy, testing) also apply.

It answers only:

> **What must be true for a v1 service to be considered architecture-compliant?**

---

# Acceptance Model

Rules are classified as:

- **MANDATORY** — failure means architecture validation is `KO`, unless an approved ADR explicitly authorizes the exception.
- **CONDITIONAL** — mandatory when the described situation exists.
- **RECOMMENDED** — deviation should be justified when material.

Rules marked **[ArchUnit]** are enforced by ArchUnit tests in `./mvnw verify`, locally and in CI. The others are checked in code review or by configuration and contract checks.

---

# 1. Status

## BL-001 — No New Services on v1

**MANDATORY**

New services must not be created with the v1 layered architecture. New services use Backend Spring v2.

Existing v1 services may receive bug fixes, security fixes, dependency upgrades and small features that fit the existing layers.

---

# 2. Structure and Dependencies

## BL-002 — Packages by Layer

**MANDATORY** **[ArchUnit]**

Application code lives under a single root package with these layer packages:

```text
controller/  service/  repository/  model/  dto/  exception/  config/
```

Classes annotated with `@RestController` reside in `..controller..`, `@Service` in `..service..`, Spring Data repositories in `..repository..`, `@Entity` in `..model..`, and `@Configuration` in `..config..`.

---

## BL-003 — Layer Dependency Direction

**MANDATORY** **[ArchUnit]**

Allowed direction:

```text
controller → service → repository
```

Forbidden dependencies:

```text
service    → controller
repository → service
repository → controller
model      → service | controller | dto | repository
```

No class may depend on `controller`.

---

## BL-004 — Controllers Never Access Repositories

**MANDATORY** **[ArchUnit]**

Controllers must not depend on repository types, `EntityManager` or `JdbcTemplate`. All data access goes through a service.

---

## BL-005 — No Package Cycles

**MANDATORY** **[ArchUnit]**

Layer packages, and functional sub-packages inside a layer, must be free of cycles.

---

# 3. API

## BL-006 — Entities Are Not Exposed Through the API

**MANDATORY** **[ArchUnit]**

Public controller methods must not accept or return `@Entity` types (directly or wrapped in `ResponseEntity`, `List` or `Page`). Requests and responses are DTOs from `..dto..`, mapped with MapStruct or hand-written mappers. ArchUnit checks raw return types; parameters and wrapped types are checked in review.

---

## BL-007 — Controllers Contain No Business Logic

**MANDATORY**

Controllers only validate input, map DTOs, call one service operation per request where practical, and select the HTTP response. Business decisions, calculations and state transitions belong to services or entities.

---

## BL-008 — Input Is Validated with Bean Validation

**MANDATORY**

Request DTOs declare their constraints with Bean Validation annotations, and controllers apply `@Valid` (or `@Validated`) on request bodies and parameters.

---

## BL-009 — Synchronous REST Only

**MANDATORY**

v1 services communicate through synchronous REST. Introducing a message broker producer or consumer into a v1 service requires an ADR, and should normally be preceded by migrating the affected module to v2.

Externally exposed REST APIs are described with OpenAPI.

---

# 4. Errors and Transactions

## BL-010 — Centralized Error Handling

**MANDATORY**

Exceptions are translated to HTTP responses by a single global `@RestControllerAdvice`, using Problem Details (`application/problem+json`).

Responses must not contain stack traces, SQL or internal class names. Controllers do not build error responses in `try/catch` blocks.

---

## BL-011 — Transactions Belong to the Service Layer

**MANDATORY** **[ArchUnit]**

`@Transactional` is declared only on classes or methods in `..service..`. Read-only operations use `@Transactional(readOnly = true)`.

`spring.jpa.open-in-view` is set to `false`.

---

# 5. Persistence

## BL-012 — Flyway Owns the Schema

**MANDATORY**

All schema changes are Flyway migrations in `db/migration`. Released migrations are never edited.

`spring.jpa.hibernate.ddl-auto` is `validate` or `none` in every non-local profile.

---

## BL-013 — Spring Data JPA Is the Default Data Access

**MANDATORY / CONDITIONAL**

Data access uses Spring Data JPA repositories with derived queries or JPQL.

Native SQL, `JdbcTemplate` or `JdbcClient` are allowed only with a short justification in the code or the pull request. A service must not read or write tables owned by another service.

---

# 6. Testing and Migration

## BL-014 — Layered Architecture Is Tested

**MANDATORY**

Each v1 service contains an ArchUnit test that checks BL-002 to BL-006 and BL-011, using `layeredArchitecture()` and `slices().should().beFreeOfCycles()`.

Persistence tests use `@DataJpaTest` against PostgreSQL in Testcontainers with Flyway enabled, not an in-memory database.

---

## BL-015 — Migration to v2 Is by Functional Module and Recorded

**CONDITIONAL**

When a v1 service starts migrating to v2:

- an ADR names the module being migrated and the target structure;
- the migrated module follows the v2 rules (AAC-001 to AAC-022) and has its own v2 ArchUnit tests;
- the v2 module does not depend on layered packages (`controller`, `service`, `repository`, `model`, `dto`);
- JPA entities are not shared between the v2 module and the remaining layered code;
- hexagonal packages (`domain`, `business`, `infrastructure`, `ports`) do not appear inside layer packages.

Mixing hexagonal packages into a layered service without an ADR is a `FAIL`.

---

# Validation Result

Architecture validation should produce a concise result such as:

```text
Architecture Validation (backend v1)

BL-001 PASS
BL-002 PASS
...
BL-015 N/A (no migration in progress)

RESULT: OK
```

For a failure:

```text
BL-004 FAIL

Expected:
Controllers never access repositories.

Observed:
OrderController depends on OrderRepository.

Evidence:
OrderController.java, LayeredArchitectureTest

RESULT: KO
```

If a v1 service cannot comply with a rule, the valid paths are to change the implementation, approve an ADR, or migrate the affected module to v2. Silently bypassing the rule is not valid.
