# High-Level Architecture

## Purpose

This document defines the architecture of the project. 

It establishes the main architectural principles, system boundaries, interaction model, component responsibilities, and the initial set of technology choices that are considered valid for the platform.

---

# Architectural Goals

- Keep the user-facing experience decoupled from backend implementation details.
- Expose a stable external business API as the main entry point to the platform.
- Support both synchronous and asynchronous internal processing.
- Allow deterministic logic and AI-assisted reasoning to coexist without mixing responsibilities.
- Support external AI/LLM providers while minimizing vendor lock-in.
- Allow the platform to evolve from a simple initial topology to independently deployable components when justified.
- Preserve clear business and technical boundaries.
- Ensure every application component follows Hexagonal Architecture principles.
- Keep infrastructure decisions replaceable where practical.
- Avoid introducing distributed-system complexity before there is a demonstrated need.
- Preserve explainability, observability, testability, and traceability across the platform.

---

# Architectural Principles

## 1. Frontend and Backend Decoupling

The frontend must remain logically decoupled from backend implementation details.
The frontend interacts with the platform through explicit external contracts and must not depend directly on:

- database structures;
- internal service topology;
- message broker topics;
- external market-data providers;
- LLM providers;
- internal domain models.

The frontend should consume business-oriented APIs.

---

## 2. Business API as Platform Entry Point

The application must expose an external business API that acts as the primary programmatic entry point to the platform.

Conceptually:

```text
Client
  │
  ▼
Business API
  │
  ▼
Application Platform
```

The Business API should expose product capabilities rather than internal technical structures.
The exact protocols and contracts are defined by the corresponding architecture decisions and the requirements of each feature definitions or enabler definition.
Rest and asynchronous communication is the preferred interaction model.

---

## 3. Optional Backend for Frontend

A Backend for Frontend (BFF) may be introduced when it provides concrete value to the frontend.

Conceptually:

```text
   Frontend
       │
       ▼
      BFF
       │
       ▼
   Business API
```

A BFF is not mandatory by default.

It should only be introduced when it helps solve concerns such as:

- frontend-specific aggregation;
- frontend-specific response shaping;
- orchestration of multiple business API calls;
- session or authentication concerns;
- reducing excessive client-to-platform round trips;
- frontend-specific caching where justified.

The BFF must not become the owner of core business rules.

Core domain behavior belongs to the corresponding backend domain capability.

---

## 4. Hexagonal Architecture and Spring Backend Structure

All business-capable backend components must follow Hexagonal Architecture principles.

For Spring Boot components, the architecture is expressed through three primary package areas:

```text
domain
business
infrastructure
```

The dependency direction is:

```text
infrastructure → business → domain
```

`infrastructure` may also depend directly on `domain` where required to implement ports or map domain types.
`domain` must not depend on `business` or `infrastructure`.
`business` must not depend on `infrastructure`.

### Domain

The `domain` package contains the business model and the ports required by the business core.

Recommended structure:

```text
domain/
├── model/
│   ├── entities / aggregates
│   ├── value objects
│   ├── enums
│   └── domain concepts
├── ports/
│   └── inbound/outbound-neutral business dependencies
└── exceptions/
    └── domain/business exceptions
```

The `domain` package contains:

- domain concepts;
- business rules and invariants that belong to the model;
- deterministic calculations that belong to domain concepts;
- enums and value objects;
- domain exceptions;
- ports used by business logic to reach persistence, remote services, messaging, AI providers, or other external capabilities.

The `domain` package must not depend on:

- Spring;
- Spring Data;
- JPA/Hibernate;
- HTTP frameworks;
- Kafka;
- database clients;
- provider SDKs;
- serialization frameworks;
- infrastructure DTOs.

Ports must use domain-oriented types and must not expose JPA entities, HTTP DTOs, Kafka records, provider payloads, or framework-specific types.

### Business

The `business` package contains the implementation of business operations and use cases.

It is responsible for:

- business-operation orchestration;
- application-level validation and coordination;
- invocation of domain behavior;
- transaction boundaries where appropriate;
- interaction with ports defined in `domain`;
- coordination between domain concepts belonging to the same functional module.

`business` may depend on `domain`.
`business` must not depend on `infrastructure`.
`business` must use ports defined in model package (that will be implemented in the `infrastructure` package).

Spring annotations may be used in `business` when they provide application/runtime behavior such as dependency injection or transaction management, 
but infrastructure-specific implementation details must remain outside the package.

### Infrastructure

The `infrastructure` package contains all adapters and framework/provider-specific implementation.

Each adapter must have an explicit package boundary.

Typical structure:

```text
infrastructure/
├── api/
│   └── rest/
│       ├── dto/
│       ├── mapper/
│       └── ...
├── persistence/
│   ├── entity/
│   ├── repository/
│   ├── mapper/
│   └── ...
├── messaging/
│   └── ...
├── client/
│   └── ...
└── <other-adapter>/
```

REST adapters must live under:

```text
infrastructure.api.rest
```

REST DTOs must live under:

```text
infrastructure.api.rest.dto
```

REST-specific mappers must live under:

```text
infrastructure.api.rest.mapper
```

Messaging adapters must live under:

```text
infrastructure.messaging
```

Persistence adapters must live under:

```text
infrastructure.persistence
```

Infrastructure may depend on `business` and `domain`.

Infrastructure implements the ports defined in `domain`.

### Modular Monolith Package Structure

When one Spring Boot deployable contains multiple functional modules, the first package boundary below the application root must represent the functional module.

Each functional module then contains its own `domain`, `business`, and `infrastructure` packages.

Conceptually:

```text
com.myfinaimanager.core
│
├── portfolio/
│   ├── domain/
│   │   ├── model/
│   │   ├── ports/
│   │   └── exceptions/
│   ├── business/
│   └── infrastructure/
│       ├── api/
│       │   ├── rest/
│       │   │   └── dto/
│       │   └── mapper/
│       ├── persistence/
│       └── messaging/
│
├── financialinstrument/
│   ├── domain/
│   ├── business/
│   └── infrastructure/
│
└── valuation/
    ├── domain/
    ├── business/
    └── infrastructure/
```

This structure preserves functional-module boundaries while applying the same architecture consistently to modular monoliths and independently deployable Spring services.

The package structure is mandatory for Spring backend components unless an ADR explicitly approves an exception.

Architecture conformance should be enforced with ArchUnit where practical.

---

# Initial System Context

At high level, the platform may evolve toward the following topology:

```text
┌─────────────────────┐
│      Investor       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Frontend.      │
└──────────┬──────────┘
           │
           │ optional
           ▼
┌─────────────────────┐
│         BFF         │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────┐
│       Business API                   │
│                                      │
│ Primary entry point to the platform  │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│        Business Core.                │
│                                      │
│ Business capability 1                │
│ Business capability 2                │
│ Business capability 3                │
│ ....                                 │
│ ....                                 │
│ Business capability n                │
└───────────┬───────────────┬──────────┘
            │               │
       synchronous      asynchronous
            │               │
            ▼               ▼
     Internal Calls     Message Bus
            │
            └───────┬───────┘
                    │
          ┌─────────▼─────────┐
          │ External Adapters │
          └───┬─────────┬─────┘
              │         │
       ┌──────▼────┐  ┌─▼─────────┐
       │ Adapter 1 │  │ Adapter n │
       └───────────┘  └───────────┘
```

This diagram represents architectural direction rather than a mandatory deployment topology.

---

# Component Topology Strategy


# Synchronous and Asynchronous Interaction

The platform supports both interaction models.

## Synchronous Interaction

Synchronous communication is appropriate when:

- the caller requires an immediate response;
- the operation is short-lived;
- strong request/response semantics are useful;
- introducing asynchronous processing would not provide meaningful benefit.

Possible mechanisms may include:

- in-process calls;
- HTTP-based APIs;
- other explicitly approved synchronous protocols.

---

## Asynchronous Interaction

Asynchronous communication is appropriate when:

- processing is long-running;
- multiple capabilities react independently;
- workloads need buffering;
- temporal decoupling is useful;
- a capability must scale independently;
- external events are ingested;
- eventual consistency is acceptable;
- business processes are naturally event-driven.

Kafka is the preferred platform technology when durable asynchronous messaging or event streaming is justified.

Conceptually:

```text
Business Event
      │
      ▼
    Kafka
      │
      ├──► Consumer A
      ├──► Consumer B
      └──► Consumer C
```

The presence of a business event in `business-events.md` does not automatically mean that the event must be published through Kafka.

That remains an architectural decision.

---

# API Architecture

The platform should distinguish between external and internal interfaces.

## Business API

The business API is the stable entry point to the platform.

It should:

- expose business capabilities;
- hide internal topology;
- maintain explicit contracts;
- provide predictable versioning;
- use stable machine-readable errors;
- avoid exposing provider-specific data structures;
- remain independent from frontend implementation.

REST APIs are an appropriate default unless another interaction model is explicitly justified.

OpenAPI should be considered the standard description mechanism for REST contracts.

---

## Internal Interfaces

Internal interactions may use:

- direct application interfaces;
- internal APIs;
- events;
- Kafka;
- scheduled workflows;
- other explicitly justified mechanisms.

Internal technical interfaces should not leak through the external business API.

---

# AI and LLM Architecture

## External Model Providers

LLM capabilities are expected to be consumed from external model providers.

Examples may include:

- AWS Bedrock;
- OpenAI;
- Anthropic;
- Google Cloud / Vertex AI;
- other approved providers.

---

## Provider Abstraction

Business capabilities must not depend directly on provider-specific SDKs or data models.

Conceptually:

```text
Domain / Application
        │
        ▼
     LLM Port
        │
        ├──► AWS Bedrock Adapter
        ├──► OpenAI Adapter
        ├──► Anthropic Adapter
        └──► Other Provider Adapter
```

Provider-specific implementation details belong in outbound adapters.

This allows:

- provider replacement;
- multi-provider strategies;
- model comparison;
- cost optimization;
- availability fallback;
- migration without changing core business logic.

---

## AI Responsibility Boundary

AI/LLM components may support capabilities such as:

- information extraction;
- classification;
- semantic reasoning;
- summarization;
- recommendation rationale generation;
- relevance analysis;
- natural-language interaction.

They must not replace deterministic calculations where deterministic algorithms exist.

AI-generated output should retain Evidence, provenance, and confidence information where relevant.

---

# Vendor Lock-In Principle

Avoiding unnecessary vendor lock-in is a cross-cutting architectural principle.

This applies not only to LLM providers but to infrastructure and external integrations in general.

The architecture should prefer:

- explicit ports and adapters;
- open standards;
- portable data representations;
- externally documented contracts;
- provider-neutral domain models;
- provider-specific logic isolated in adapters.

Examples:

```text
Business Domain
      │
      ▼
Market Data Port
      │
      ├──► Provider A
      └──► Provider B
```

or:

```text
Business Domain
      │
      ▼
LLM Port
      │
      ├──► AWS Bedrock
      └──► Another Provider
```

Provider abstractions should not be introduced as speculative complexity, but clear external boundaries should not leak provider-specific concepts into the domain.

---

# Persistence Architecture

## PostgreSQL

PostgreSQL is the preferred general-purpose relational persistence technology.

It is suitable for information such as:

- Investors;
- Portfolios;
- Positions;
- investment information;
- reviews;
- recommendations;
- configuration;
- transactional business state.

Exact data ownership and schemas are defined by implementation plans and architecture decisions.

For Spring Boot components using relational persistence, Spring Data JPA is the standard persistence abstraction.

The expected architecture is:

```text
domain.port
    ↑ implemented by
infrastructure.persistence adapter
    ↓ delegates to
Spring Data JpaRepository
    ↓
JPA entities
    ↓
PostgreSQL
```

JPA entities are infrastructure models and must not be used as canonical domain models.

Domain classes must not carry JPA persistence annotations.

Spring Data derived queries, specifications, criteria, or explicitly justified repository queries should be preferred over embedding general-purpose SQL in business-facing repository adapters.

Direct JDBC or handwritten SQL is conditional and requires a concrete technical reason.

Flyway remains responsible for relational schema evolution.

---

## Neo4j

Neo4j is an allowed specialized persistence technology for graph-oriented use cases where graph traversal or semantic relationships provide concrete product value.

Potential uses include:

- relationships between companies;
- sectors;
- industries;
- countries;
- risks;
- market events;
- news;
- dependencies;
- portfolio exposures;
- semantic reasoning.

Conceptually:

```text
Portfolio
   │ HOLDS
   ▼
Financial Instrument
   │ REPRESENTS
   ▼
Company
   │ OPERATES_IN
   ▼
Country

Company
   │ EXPOSED_TO
   ▼
Risk
```


Its use should be justified by a concrete capability.

---

## Additional Persistence Technologies

Other persistence technologies may be introduced if required by specific workloads.

Examples could include:

- object storage for large documents;
- search engines for full-text retrieval;
- vector-capable persistence for semantic retrieval;
- caches for performance-sensitive workloads.

Their introduction requires explicit architectural justification and should normally be captured in an ADR.

---

# Technology Direction

The following technologies form the initial approved or expected technology space.

This section does not make every technology mandatory.

| Area | Technology | Initial Position |
|---|---|---|
| Web Frontend | Angular | Preferred / Approved |
| Backend | Spring Boot | Approved |
| Spring Build Tool | Maven | Standard / Required for Spring components |
| Spring Relational Persistence | Spring Data JPA / Hibernate | Preferred standard |
| Backend / AI / Data | Python | Approved |
| External Business API | REST + OpenAPI | Preferred default |
| Asynchronous Messaging | Kafka | Approved when justified |
| Relational Persistence | PostgreSQL | Preferred default |
| Graph Persistence | Neo4j | Approved when graph use case is justified |
| External AI | AWS Bedrock and other providers | Approved behind abstraction |
| Observability | OpenTelemetry | Preferred standard |
| Containerization | Docker / OCI containers | Preferred |
| API Authentication | OAuth 2.0 / OpenID Connect | Preferred direction |

Detailed versions, restrictions, and classifications belong in `technology-policy.md`.

---

# Java / Spring and Python Coexistence

Spring Boot and Python are both valid backend technologies.

The platform must avoid arbitrary fragmentation between them.

Technology selection should be based on capability characteristics.

Spring Boot may be particularly suitable for:

- transactional domain capabilities;
- business APIs;
- strong domain models;
- integration-heavy backend services.

Python may be particularly suitable for:

- AI workflows;
- data processing;
- quantitative analytics;
- model integration;
- experimentation;
- specialized financial/data libraries.

This does not imply that both runtimes must be introduced immediately.

An initial implementation may use only one backend runtime.

Introducing a second runtime should have a concrete justification.

---

# Cross-Cutting Concerns

## Observability

All deployable components should support appropriate observability.

OpenTelemetry is the preferred vendor-neutral observability standard.

The platform should be capable of producing:

- logs;
- metrics;
- distributed traces.

Correlation should be preserved across synchronous and asynchronous flows where applicable.

---

## Security

Security architecture must evolve with product requirements.

Expected principles include:

- authenticated access to private portfolio information;
- authorization around Investor-owned resources;
- encryption in transit;
- secure secret management;
- no secrets in source control;
- least-privilege access to external providers.

OAuth 2.0 and OpenID Connect are the preferred standards for identity-related integration unless an ADR establishes otherwise.

---

## Data Privacy

Portfolio information is private user data.

Architecture must avoid unnecessary propagation of portfolio information to external services.

When external AI providers are used, only the information required for the specific use case should be shared.

Sensitive or private information must not be included in prompts or external requests without explicit product and security consideration.

---

## Explainability and Provenance

Important analytical results should preserve enough information to explain:

- which inputs were used;
- which deterministic calculations were performed;
- which external information contributed;
- which AI provider/model participated where relevant;
- which Evidence supports an interpretation or recommendation.

---

# Architecture Diagrams

Architecture diagrams should be maintained under:

```text
reference/engineering/diagrams
```

They should evolve as architecture changes.

---

# Architecture Decision Records

ADRs must document the problem, issue or was detected, why a decision was taken, alternatives considered, and its consequences.
Significant architectural decisions must be documented under:

```text
reference/engineering/adrs
```

---

# Implementation Model

The current executable must live under:

```text
implementation/platform/
├── backend/
├── contracts/
├── frontend/
├── infrastructure/
├── start.sh
└── stop.sh
```

This structure is part of the architectural organization of the repository.

## Frontend

`implementation/platform/frontend/` contains user-facing frontend applications.

The initial web frontend is expected to use Angular.

Frontend applications remain decoupled from backend implementation details and interact through approved contracts.

## Backend

`implementation/platform/backend/` contains backend deployable components or bounded services.

A directory directly under `backend/` represents a backend deployable unit or independently bounded backend component.

Initial service granularity may deliberately be coarse. A backend service may initially implement several functional domains while preserving clear modular boundaries internally.

Service boundaries may later become finer when justified by independent scalability, maintainability, ownership, different runtime needs, availability requirements, release cadence, security isolation, or operational characteristics.

Functional domains do not automatically map one-to-one to directories under `backend/`.

Each backend component must follow the architecture rules defined by this project.

Spring Boot components must use the standard `domain / business / infrastructure` package model.

When a backend deployable contains multiple functional modules, it must organize code module-first and layer-second:

```text
<functional-module>/
├── domain/
├── business/
└── infrastructure/
```

Spring Boot components use Maven as their standard build tool.

## Contracts

`implementation/platform/contracts/` contains platform contracts that represent the current externally visible interfaces of the executable system.

Examples include OpenAPI contracts and AsyncAPI contracts when asynchronous interfaces exist.

Contracts represent the current platform, not isolated copies per Feature Definition. A vertical feature may evolve these contracts.

## Infrastructure

`implementation/platform/infrastructure/` contains infrastructure required to execute, test, and deploy the current platform.

Infrastructure is introduced incrementally and only when justified by implemented capabilities.

## Platform Lifecycle Scripts

The platform exposes stable local lifecycle entry points through:

```text
implementation/platform/start.sh
implementation/platform/stop.sh
```

`start.sh` is the canonical local entry point for starting the complete executable platform or development environment.

`stop.sh` is the canonical local entry point for stopping it.

These scripts may delegate to Docker Compose, service-specific tooling, frontend tooling, or other mechanisms.

---

# Architecture Evolution

The architecture should evolve incrementally.

The preferred lifecycle is:

```text
Product Requirement
       ↓
Architecture Impact Analysis
       ↓
Does current architecture support it?
       │
       ├── Yes ───────────► Implementation Plan
       │
       └── No
             ↓
       Architecture Decision
             ↓
             ADR
             ↓
       Update Architecture
             ↓
       Update Diagrams
             ↓
       Implementation Plan
```

Architecture should not anticipate every future requirement.

However, intentional boundaries should make future evolution possible without forcing premature distribution.

---
