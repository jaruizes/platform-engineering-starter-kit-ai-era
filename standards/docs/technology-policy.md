# Technology Policy

## Purpose

This document defines the **approved technology stack and technology guardrails**.

Its purpose is to constrain implementation choices made by humans, AI agents, or SDD frameworks.

It does not explain architecture, testing strategy, delivery workflow, or feature behavior.

Those concerns belong to their corresponding reference or definition documents.

The governing rule is:

> **Use technologies from this policy by default.  
> Introducing a technology outside this policy requires an explicit architectural decision.**

---

# Policy Statuses

- **REQUIRED** — must be used for the applicable concern unless an approved ADR defines an exception.
- **PREFERRED** — default choice when the concern exists.
- **ALLOWED** — approved option; use when justified by the capability.
- **CONDITIONAL** — may only be introduced when a concrete requirement or quality attribute justifies it.
- **ADR REQUIRED** — may be introduced only after an approved ADR.
- **NOT APPROVED** — must not be introduced unless this policy is explicitly changed through architectural governance.

---

# Approved Technology Stack

| Concern | Technology / Standard | Status | Guardrail |
|---|---|---|---|
| Web Frontend | Angular | PREFERRED | Default web frontend framework |
| Frontend Language | TypeScript | REQUIRED | Required for Angular frontend code |
| Java Backend | Spring Boot | ALLOWED | Primary Java backend framework |
| Spring Build Tool | Maven | REQUIRED | Gradle requires an approved architectural exception |
| Python Backend / AI / Data | Python | ALLOWED | Use only when capability characteristics justify it |
| Python API Framework | FastAPI | ALLOWED | Preferred option when Python exposes HTTP APIs |
| External Business API | REST | PREFERRED | Default external synchronous interaction style |
| REST Contract | OpenAPI | REQUIRED | Required for externally exposed REST APIs |
| Asynchronous Messaging | Kafka | CONDITIONAL | Use only when asynchronous decoupling or streaming provides concrete value |
| Event Contract | AsyncAPI | PREFERRED | Use for externally exposed asynchronous contracts where applicable |
| Relational Database | PostgreSQL | PREFERRED | Default relational persistence technology |
| Spring Relational Persistence | Spring Data JPA / Hibernate | REQUIRED | Default abstraction for Spring relational persistence |
| Direct SQL / JDBC | JdbcClient / JdbcTemplate / JDBC / native SQL | CONDITIONAL | Requires explicit technical justification |
| Schema Migration | Flyway | PREFERRED | Default relational schema evolution mechanism |
| Vector Search | PostgreSQL + pgvector | PREFERRED | Evaluate before introducing dedicated vector infrastructure |
| Dedicated Vector Database | Specialized provider/database | ADR REQUIRED | Only when PostgreSQL/pgvector is insufficient |
| Graph Database | Neo4j | CONDITIONAL | Only when graph traversal/relationships provide demonstrated value |
| Full-Text Search | PostgreSQL | PREFERRED | Evaluate before introducing dedicated search infrastructure |
| Search Engine | OpenSearch / Elasticsearch | ADR REQUIRED | Only for workloads that justify dedicated search infrastructure |
| Cache | Redis-compatible technology | CONDITIONAL | Only for demonstrated performance/load needs |
| AI Provider | AWS Bedrock | ALLOWED | Must remain behind provider-neutral application boundaries |
| AI Provider | OpenAI | ALLOWED | Must remain behind provider-neutral application boundaries |
| AI Provider | Anthropic | ALLOWED | Must remain behind provider-neutral application boundaries |
| AI Provider | Google Vertex AI | ALLOWED | Must remain behind provider-neutral application boundaries |
| AI Integration Boundary | Provider-neutral ports/adapters | REQUIRED | Business/domain logic must not depend on provider SDKs |
| MCP | Model Context Protocol | CONDITIONAL | Use when agent/tool interoperability provides concrete value |
| Observability | OpenTelemetry | PREFERRED | Application-facing vendor-neutral observability standard |
| Logging | Structured logging | REQUIRED | Logs must be machine-readable |
| Containers | OCI-compatible containers | PREFERRED | Docker-compatible tooling is approved |
| Authentication | OAuth 2.0 / OpenID Connect | PREFERRED | Default identity standards |
| Authorization | Backend-enforced application/domain policies | REQUIRED | Frontend checks are not a security boundary |
| Infrastructure as Code | Terraform | ALLOWED | Preferred when infrastructure requires reproducible provisioning |
| Deployment | Kubernetes | CONDITIONAL | Introduce only when deployment/operational needs justify it |
| CI/CD | GitHub Actions | ALLOWED | Default repository CI/CD platform |
| Secrets | External secret management | REQUIRED for deployed environments | Secrets must never be committed |
| Java Testing | JUnit 5 | PREFERRED | Default Java test framework |
| Java Assertions | AssertJ | PREFERRED | Default fluent assertion library |
| Java Mocking | Mockito | ALLOWED | Use where isolation is appropriate |
| Python Testing | pytest | PREFERRED | Default Python test framework |
| Infrastructure Integration Testing | Testcontainers | REQUIRED when applicable | Use for application-managed infrastructure when a suitable container exists |
| Architecture Testing | ArchUnit | PREFERRED for Java | Use where architecture constraints are mechanically enforceable |
| Browser E2E | Playwright | PREFERRED | Default browser E2E framework |
| Initial E2E Browser | Chromium | PREFERRED | Additional browsers require explicit justification |

---

# Technology Guardrails

## 1. Keep Technology Choices Requirement-Driven

Do not introduce a technology merely because it is approved or fashionable.

A technology must solve a concrete product, architecture, engineering, operational, or quality need.

---

## 2. Avoid Duplicate Technologies for the Same Concern

Do not introduce multiple frameworks, runtimes, databases, brokers, or infrastructure products solving the same concern without a concrete reason.

Examples:

```text
Spring Boot + another Java backend framework
Kafka + another broker
PostgreSQL + another relational database
multiple vector databases
multiple observability SDK standards
```

require explicit justification.

---

## 3. Keep External Providers Replaceable

Provider-specific SDKs and payloads must stay inside adapters or equivalent infrastructure boundaries.

This applies especially to:

- AI/LLM providers;
- market-data providers;
- news providers;
- identity providers;
- cloud-managed external services.

Provider-specific types must not become domain/application contracts.

---

## 4. Prefer Open Standards

Prefer open or portable standards where applicable, including:

```text
OpenAPI
AsyncAPI
OAuth 2.0
OpenID Connect
OpenTelemetry
OCI
MCP
```

Use of an open standard does not imply that every capability must adopt it.

---

## 5. Preserve the Deterministic Boundary

AI/LLM technology must not replace deterministic calculations or validations when a deterministic implementation is appropriate.

AI providers may interpret, classify, summarize, reason over, or explain deterministic results.

---

## 6. Specialized Infrastructure Must Earn Its Complexity

The following technologies are not part of the default bootstrap unless a concrete capability justifies them:

```text
Kafka
Neo4j
Redis
OpenSearch / Elasticsearch
dedicated vector databases
Kubernetes
additional backend runtimes
additional deployable services
workflow engines
additional databases
```

---

## 7. Spring Technology Baseline

When Spring Boot is selected:

```text
Build            Maven
Persistence      Spring Data JPA / Hibernate
Schema migration Flyway
Testing          JUnit 5
Architecture     ArchUnit where applicable
Integration      Testcontainers where applicable
```

Direct JDBC or hand-written/native SQL is an exception, not the default.

---

## 8. Testing Technology Must Follow Testing Strategy

This document defines approved testing tools only.

What must be tested, required test levels, E2E scope, coverage expectations, AI evaluation strategy, and validation evidence belong in:

```text
product/reference/engineering/testing-strategy.md
```

A technology choice must not weaken those requirements.

---

# Technology Introduction

If implementation requires a technology not listed as REQUIRED, PREFERRED, ALLOWED, or CONDITIONAL:

```text
Need identified
      ↓
Can approved stack satisfy it?
      │
      ├── Yes → use approved technology
      │
      └── No
            ↓
      evaluate alternatives
            ↓
      architecture decision / ADR
            ↓
      update technology-policy.md
            ↓
      implementation
```

AI agents and SDD frameworks must not introduce unapproved technologies silently.

---

# Technology Replacement

Replacing an architecturally significant technology requires explicit evaluation and should normally be captured by an ADR.

Relevant considerations include:

- product impact;
- migration impact;
- data compatibility/migration;
- operational impact;
- contract compatibility;
- security;
- observability;
- rollback.

---

# Version Policy

This policy defines **technology families and standards**, not exact dependency versions.

Exact versions belong in executable project configuration and must be pinned or constrained appropriately.

Version selection should favor:

- actively supported releases;
- security support;
- ecosystem compatibility;
- operational stability.

---

# Validation Principle

An implementation is technology-policy compliant when:

1. every introduced technology appears in the approved matrix with an applicable status;
2. all `REQUIRED` technologies/standards are respected where their concern applies;
3. every `CONDITIONAL` technology has a concrete justification;
4. every `ADR REQUIRED` technology has an approved ADR;
5. no `NOT APPROVED` or undocumented technology has been introduced;
6. provider-specific implementation remains behind the architectural boundaries defined in `architecture.md`;
7. the implementation follows `architecture-rules.md`.

A technology-policy violation is a blocking validation finding unless an approved architecture decision explicitly authorizes it.

---

# Governing Principle

> **`architecture.md` defines the architectural solution space.  
> `architecture-rules.md` defines architecture conformance.  
> `technology-policy.md` defines the technologies allowed to materialize that architecture.**
