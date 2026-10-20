# Architecture Rules

## Purpose

This document defines the concise, verifiable architecture acceptance criteria and rules for this project.

It does **not** restate the architecture. The authoritative architectural intent, rationale, structure, interaction model, technology direction, persistence strategy, AI boundaries, observability principles, implementation model, and evolution model are defined in:

```text
product/reference/engineering/architecture.md
```

This document answers only:

> **What must be true for an implementation to be considered architecture-compliant?**

Where more detail is needed, the validator must refer to `architecture.md` and the applicable ADR.

---

# Acceptance Model

Rules are classified as:

- **MANDATORY** — failure means architecture validation is `KO`, unless an approved ADR explicitly authorizes the exception.
- **CONDITIONAL** — mandatory when the described situation exists.
- **RECOMMENDED** — deviation should be justified when material.

Architecture conformance should be automated where practical.

---

# 1. Core Architecture

## AAC-001 — Hexagonal Architecture

**MANDATORY**

Backend business-capable components must follow the Hexagonal Architecture defined in `architecture.md`.

For Spring Boot:

```text
<functional-module>/
├── domain/
├── business/
└── infrastructure/
```

For a modular monolith, the functional module is the first package boundary.

---

## AAC-002 — Dependency Direction

**MANDATORY**

Forbidden dependencies:

```text
domain   → business
domain   → infrastructure
business → infrastructure
```

Allowed direction:

```text
infrastructure → business → domain
```

`infrastructure` may depend directly on `domain` when implementing ports or mapping domain types.

This rule must be enforced with ArchUnit where applicable.

---

## AAC-003 — Domain and Business Independence

**MANDATORY**

`domain` must remain independent from framework/provider-specific concerns.

It must not expose or depend on Spring, JPA, HTTP DTOs, Kafka records, database clients, provider SDK models, or infrastructure types.

`business` owns use-case orchestration and must not depend on `infrastructure`.

Business behavior must not be hidden inside controllers, persistence adapters, messaging adapters, provider clients, or frontend code.

---

## AAC-004 — Infrastructure Owns Adapters

**MANDATORY**

Framework and provider-specific implementation belongs under `infrastructure`.

Applicable Spring package conventions defined in `architecture.md` must be respected, including REST, persistence, messaging and client adapters.

---

# 2. Boundaries and Ownership

## AAC-005 — Functional Domain Does Not Imply Deployment Boundary

**MANDATORY**

A functional domain must not automatically become a:

- microservice;
- database;
- Kafka topic;
- deployment unit.

A new deployment boundary requires explicit architectural justification.

---

## AAC-006 — Module Ownership Is Preserved

**MANDATORY**

Each module owns its business behavior and persistence representation.

A module must not directly read or write another module's tables, persistence entities or specialized store representation.

Cross-module collaboration must use an explicit published interface, port, API, event, or approved contract.

Sharing a physical PostgreSQL instance does not imply shared ownership.

---

## AAC-007 — Service Extraction Requires Evidence

**MANDATORY**

A module may become an independently deployable service only when justified by a concrete need such as independent scaling, availability, security, runtime, release cadence, resource profile or operational ownership.

Significant extraction requires an ADR.

---

# 3. API and Frontend

## AAC-008 — Business API Is the External Boundary

**MANDATORY**

External clients must use approved business-oriented contracts.

External contracts must not expose:

- internal topology;
- persistence structures;
- provider-specific payloads;
- internal topics;
- internal AI/provider concepts.

Externally exposed REST APIs must be described with OpenAPI.

---

## AAC-009 — Frontend Is Decoupled

**MANDATORY**

The frontend must use approved frontend-facing contracts.

It must not directly access databases, consume internal messaging, invoke LLM/data providers, depend on persistence models, or own critical backend business rules.

A BFF may only be introduced when it provides concrete frontend-specific value and must not own core business behavior.

---

# 4. Interaction and Messaging

## AAC-010 — Interaction Style Is Requirement-Driven

**MANDATORY**

Synchronous or asynchronous communication must be selected because the use case requires it.

The availability of Kafka or another broker is not sufficient justification.

---

## AAC-011 — Technical Messaging Is Explicitly Designed

**CONDITIONAL**

When a business event is exposed through technical messaging, the architecture must define the relevant:

- producer and consumers;
- schema/contract;
- versioning and compatibility;
- delivery semantics;
- ordering/idempotency expectations where applicable;
- observability.

A business event does not automatically imply Kafka publication.

Distributed ACID transactions across independently deployable components are not accepted.

---

# 5. Persistence

## AAC-012 — Persistence Technology Follows the Approved Model

**MANDATORY / CONDITIONAL**

PostgreSQL is the preferred relational store.

For Spring relational persistence:

```text
Spring Data JPA / Hibernate
```

is the standard abstraction.

JPA entities are infrastructure models and must not become domain models.

Direct JDBC, `JdbcClient`, `JdbcTemplate`, native SQL or hand-written SQL require explicit technical justification.

Flyway owns relational schema evolution.

---

## AAC-013 — Specialized Infrastructure Requires Demonstrated Value

**MANDATORY**

Neo4j, vector databases, search engines, caches, additional databases or other specialized persistence technologies must not be introduced speculatively.

If the same business change affects several stores or external systems, an explicit consistency strategy is required. Accidental dual writes are not accepted.

---

# 6. External Providers and AI

## AAC-014 — Provider Boundaries Are Replaceable

**MANDATORY**

Architecturally significant external providers must be isolated behind explicit ports/adapters or equivalent boundaries.

Provider-specific payloads and SDK models must not define the domain model.

Vendor-neutrality must not be used to justify meaningless or speculative abstractions.

---

## AAC-015 — AI Does Not Replace Deterministic Logic

**MANDATORY**

LLMs must not replace calculations or validations that can be implemented reliably and deterministically.

AI may interpret, classify, summarize or explain deterministic results.

AI-generated interpretations/recommendations must remain distinguishable from verified facts, observed data and deterministic calculations.

Material AI conclusions should preserve evidence/provenance where relevant.

---

# 7. Security, Observability and Resilience

## AAC-016 — Security Boundaries Are Preserved

**MANDATORY**

- Secrets must not be committed to source control.
- Private data shared with external providers must be minimized to what the approved use case requires.
- Authorization for user-owned resources must be enforced backend-side when authorization exists.

---

## AAC-017 — Deployable Components Are Observable

**MANDATORY**

Deployable backend components must provide appropriate structured logs, metrics and traces where useful.

OpenTelemetry is the preferred vendor-neutral observability standard.

Correlation must cross relevant synchronous, asynchronous and external-provider boundaries.

Important analytical/business outcomes must preserve sufficient evidence for explainability or auditability where required by the use case.

---

## AAC-018 — External Failures Are Bounded

**MANDATORY**

External failures must not leave authoritative business state partially corrupted.

Remote calls require explicit bounded timeouts.

Retries, when used, must consider idempotency, backoff, rate limits and failure amplification.

---

# 8. Architecture Evolution

## AAC-019 — No Speculative Infrastructure

**MANDATORY**

Significant infrastructure must not be introduced before a concrete requirement or quality attribute justifies it.

Examples include:

- Kafka;
- Kubernetes;
- Neo4j;
- Redis;
- OpenSearch;
- additional databases;
- additional deployable services;
- workflow engines.

---

## AAC-020 — Architectural Change Is Explicit

**MANDATORY**

Significant architecture changes or deviations require an ADR.

Architecture documents and diagrams must be updated when the approved architecture changes.

Speculative future components must not be represented as current reality.

---

# 9. Repository and Conformance

## AAC-021 — Executable Platform Structure

**MANDATORY**

The executable platform must live under:

```text
implementation/platform/
```

and preserve the implementation model defined in `architecture.md`.

The canonical local lifecycle entry points remain:

```text
implementation/platform/start.sh
implementation/platform/stop.sh
```

---

## AAC-022 — Architecture Is Automatically Checked Where Practical

**MANDATORY where enforceable**

Architecture constraints must be verified automatically when suitable mechanisms exist.

Examples include:

- ArchUnit dependency/package rules;
- OpenAPI validation;
- dependency scanning;
- forbidden-import checks;
- architecture tests.

AI-generated code is subject to exactly the same constraints as human-written code.

---

# Validation Result

Architecture validation should produce a concise result such as:

```text
Architecture Validation

AAC-001 PASS
AAC-002 PASS
...
AAC-022 PASS

RESULT: OK
```

For a failure:

```text
AAC-006 FAIL

Expected:
Module boundaries are respected.

Observed:
Module A directly reads Module B persistence representation.

Evidence:
<file / package / test / dependency>

RESULT: KO
```

If an implementation cannot comply with an accepted architecture rule, the valid paths are:

```text
change the implementation
```

or:

```text
approve an architecture change / ADR
```

Silently bypassing the rule is not valid.

---

# Governing Principle

> **`architecture.md` explains the architecture.  
> `architecture-acceptance.md` defines the concise conformance contract used by humans and automated validators.**
