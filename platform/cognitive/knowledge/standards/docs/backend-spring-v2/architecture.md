# Backend architecture v2: hexagonal Spring

## Purpose

Backend v2 is the reference architecture for new backend services built with Spring Boot. It uses module-first packages and hexagonal boundaries: `domain`, `business`, and `infrastructure`. Backend v1 remains for maintenance of existing layered services.

This document defines technology and architecture constraints. Product terminology, business rules, and capability-specific requirements belong to each service's product definition and approved domain model.

---

# Architectural Goals

- Keep domain behavior independent from frameworks, transport protocols, and persistence.
- Keep clients decoupled from internal service topology and storage details.
- Make module ownership and dependency direction explicit.
- Select synchronous or asynchronous communication based on use-case needs.
- Keep external providers replaceable where that provides value.
- Preserve observability, testability, and traceability.
- Avoid distributed-system complexity and infrastructure without a demonstrated need.
- Apply the same architecture constraints to human-written and generated code.

---

# Architectural Principles

## 1. Explicit Contracts

When a capability is consumed across a system boundary, define an explicit contract appropriate to its consumers. REST with OpenAPI is the preferred default for synchronous HTTP APIs. Use other protocols or asynchronous contracts when the use case justifies them.

Contracts should expose stable capability-level operations and data. They should not expose persistence models, provider payloads, internal topics, or framework types. A service that has no external consumers does not need an external API solely to satisfy this architecture.

## 2. Hexagonal Architecture and Spring Structure

Business-capable backend components follow hexagonal architecture. For Spring Boot, the primary package areas are:

```text
<module>/
├── domain/
├── business/
└── infrastructure/
```

The dependency direction is:

```text
infrastructure → business → domain
```

`infrastructure` may depend directly on `domain` to implement ports or map domain types. `domain` must not depend on `business` or `infrastructure`; `business` must not depend on `infrastructure`.

### Domain

The `domain` package contains domain concepts, invariants, value types, domain exceptions, and ports needed by the core. It must not depend on Spring, JPA, HTTP frameworks, messaging records, database clients, serialization frameworks, provider SDKs, or infrastructure DTOs.

Ports use domain-oriented types. They must not expose persistence entities, transport DTOs, framework types, or provider-specific payloads.

### Business

The `business` package implements application operations and coordinates domain behavior. It may perform application-level validation, define transaction boundaries, and invoke domain ports. It must not contain transport or provider-specific implementation details.

Spring annotations may be used for application/runtime behavior such as dependency injection and transaction management.

### Infrastructure

The `infrastructure` package contains framework- and provider-specific adapters. Keep each adapter in a clear package boundary. Typical areas include:

```text
infrastructure/
├── api/rest/{dto,mapper}/
├── persistence/{entity,repository,mapper}/
├── messaging/
└── client/
```

REST adapters, persistence adapters, messaging adapters, and external-client adapters translate between their technical contracts and domain/application types.

## 3. Module Boundaries

In a modular monolith, the first package boundary below the application root represents the module. Each module owns its `domain`, `business`, and `infrastructure` packages.

```text
com.example.application
├── <module-a>/{domain,business,infrastructure}
└── <module-b>/{domain,business,infrastructure}
```

A module owns its behavior and persistence representation. Modules must not read or write one another's tables, entities, or specialized storage models. Cross-module collaboration uses an explicit published interface, port, API, event, or approved contract.

A functional module does not automatically imply a separate service, database, broker topic, or deployment unit. Extract a module only when a concrete operational or quality need supports the boundary; document significant changes with an ADR.

## 4. Interaction and Messaging

Use synchronous communication when the caller needs an immediate response and request/response semantics fit. Use asynchronous communication when it provides concrete value such as temporal decoupling, buffering, long-running processing, or independent consumers.

The availability of a broker does not by itself justify messaging. When events are published, define ownership, schema, compatibility, delivery semantics, ordering/idempotency expectations, and observability. Avoid distributed transactions; specify consistency and failure handling across boundaries.

## 5. Persistence

PostgreSQL is the preferred general-purpose relational store for this starter kit. For Spring relational persistence, Spring Data JPA/Hibernate is the default abstraction and Flyway manages schema evolution.

Persistence entities are infrastructure models. They are not canonical domain types and do not belong in domain ports. Prefer repository abstractions and explicit mapping. Direct JDBC or handwritten SQL requires a concrete technical reason.

Specialized stores, caches, search engines, or additional databases require a demonstrated workload or capability need and an explicit consistency strategy where data is written across stores. Record significant choices in an ADR.

## 6. External Providers and Optional AI

Integrations with external providers belong behind infrastructure adapters. Keep provider SDKs and payloads out of the domain. Introduce an abstraction when it protects a meaningful boundary; avoid speculative wrappers.

If a service uses AI/LLM capabilities, do not use probabilistic output in place of deterministic calculations or validations. Validate structured output, define failure behavior, and retain relevant provenance. AI adoption is optional and driven by a product need.

## 7. Security, Privacy, and Resilience

- Keep secrets out of source control and use the approved secret-delivery mechanism.
- Apply authentication and authorization at the appropriate backend boundary when required.
- Enforce resource ownership and access scope server-side.
- Minimize private or confidential data sent to external providers.
- Use bounded timeouts for remote calls. Retries must account for idempotency, backoff, rate limits, and failure amplification.
- External failures must not leave authoritative state partially corrupted.

## 8. Observability

Deployable components should provide appropriate structured logs, metrics, and traces. OpenTelemetry is the preferred vendor-neutral standard. Preserve correlation across synchronous, asynchronous, and external-provider boundaries where applicable. Logs and telemetry must not expose secrets or unnecessary sensitive data.

## 9. Technology Direction

The initial technology choices for this starter kit are:

| Area | Technology | Position |
|---|---|---|
| Backend runtime | Spring Boot | Approved |
| Build tool | Maven | Standard for Spring services |
| Relational persistence | PostgreSQL | Preferred default |
| Spring persistence | Spring Data JPA / Hibernate | Preferred default |
| Schema migration | Flyway | Preferred default |
| HTTP API contracts | REST + OpenAPI | Preferred default |
| Asynchronous messaging | Kafka | Use when justified |
| Observability | OpenTelemetry | Preferred standard |
| Containers | Docker / OCI | Preferred |
| Identity protocols | OAuth 2.0 / OpenID Connect | Preferred when identity integration is required |

Detailed versions and restrictions belong in `../common/technology-policy.md`. This table does not make optional technologies mandatory.

## 10. Repository and Architecture Evolution

The executable platform in this starter kit is organized under:

```text
implementation/platform/
├── backend/
├── contracts/
├── frontend/
├── infrastructure/
├── start.sh
└── stop.sh
```

Service repositories may use a different physical layout when their approved architecture and build tooling require it. Significant architecture changes require an ADR. Keep architecture documents and diagrams aligned with approved decisions, and do not represent speculative components as current reality.

The canonical local lifecycle entry points remain `implementation/platform/start.sh` and `implementation/platform/stop.sh` for this starter kit.
