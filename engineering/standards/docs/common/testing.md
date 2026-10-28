# Testing

## Purpose

This document defines the **testing approach**.

Its purpose is to describe how implementation correctness and integration behavior should be verified across the platform.

It does **not** define:

- delivery workflow;
- TDD process;
- Definition of Done;
- CI/CD stages;
- coverage gates;
- feature-specific acceptance criteria;
- architecture rules themselves.

Those concerns belong to the corresponding governance, architecture, or Feature / Enabler Definition documents.

The governing principle is:

> **Testing should provide meaningful evidence that the implementation behaves correctly at the appropriate level.**

---

# 1. Testing Principles

Testing must follow these principles:

1. Test behavior, not implementation details.
2. Prefer the lowest test level that can prove the behavior reliably.
3. Keep tests deterministic unless the behavior itself is probabilistic.
4. Use real application-managed infrastructure in integration tests where practical.
5. Mock or stub true external providers at explicit adapter boundaries.
6. Validate externally visible contracts.
7. Verify enforceable architecture constraints automatically where practical.
8. Use browser E2E tests only for high-value journeys across realistic system boundaries.
9. AI-enabled behavior requires evaluation in addition to traditional deterministic testing.
10. Test data must be safe, understandable, and reproducible.

---

# 2. Unit and Domain Tests

## Purpose

Unit/domain tests validate isolated deterministic behavior quickly.

They are appropriate for:

- business rules;
- domain invariants;
- value objects;
- validation;
- deterministic calculations;
- state transitions;
- pure transformations;
- domain policies.

Tests should:

- run quickly;
- avoid network access;
- avoid real infrastructure;
- use meaningful assertions;
- use product/domain terminology;
- cover relevant normal, boundary, and failure scenarios.

Implementation details should not be tested unless they are themselves part of an explicit contract.

---

# 3. Integration Tests

## Purpose

Integration tests verify that application code integrates correctly with real infrastructure owned or operated by the application.

Typical examples include:

- PostgreSQL;
- Kafka;
- Neo4j;
- identity infrastructure;
- filesystem/object storage where locally reproducible;
- HTTP adapter wiring against a controlled test server.

## Testcontainers

Testcontainers is the default approach for infrastructure integration when a reliable compatible container exists.

Integration tests should be:

- reproducible;
- isolated;
- self-contained;
- independent from manually installed developer infrastructure;
- safe to execute in automation.

Infrastructure must not be replaced by a mock when the purpose of the test is to verify that infrastructure integration itself.

Integration tests should verify relevant concerns such as:

- persistence mappings;
- migrations;
- database constraints;
- transaction behavior;
- repository adapters;
- serialization;
- message production/consumption;
- idempotency;
- infrastructure failure translation;
- query behavior.

If Testcontainers cannot reasonably be used, the alternative strategy must be explicit.

---

# 4. External Provider Testing

External providers must be tested at adapter boundaries.

Examples include:

- market-data providers;
- news providers;
- LLM providers;
- external SaaS APIs;
- payment/identity providers when not owned by the application.

## Local / Normal Verification

Use deterministic:

- stubs;
- fixtures;
- mock servers;
- recorded synthetic responses;

when live calls would introduce:

- cost;
- nondeterminism;
- rate limits;
- privacy risk;
- instability;
- external network dependency.

Normal verification must not depend on live external providers.

## Provider Compatibility Tests

Optional or scheduled compatibility tests may call real providers when justified.

These tests should remain separate from normal deterministic verification because they may be:

- slow;
- costly;
- rate-limited;
- externally unstable.

---

# 5. Contract Tests

## REST Contracts

Externally exposed REST APIs must be validated against their OpenAPI contracts.

Contract verification should cover relevant:

- request schemas;
- response schemas;
- required fields;
- status codes;
- error payloads;
- validation behavior;
- compatibility expectations.

Implementation and contract must not drift silently.

## Event Contracts

When asynchronous interfaces are externally exposed, tests should verify relevant:

- event schema;
- required fields;
- serialization/deserialization;
- compatibility/versioning;
- producer expectations;
- consumer expectations.

AsyncAPI should be used where required by the architecture/technology policy.

---

# 6. Architecture Tests

Architecture constraints should be verified automatically where practical.

For Java / Spring, ArchUnit is the preferred tool.

Typical checks include:

```text
domain   !→ business
domain   !→ infrastructure
business !→ infrastructure
```

and, where applicable:

- module-first package organization;
- adapters remain under infrastructure;
- provider SDKs remain inside adapters;
- forbidden cross-module dependencies;
- forbidden direct persistence access;
- REST / messaging / persistence package placement.

Equivalent checks should be used for other runtimes where practical.

The authoritative conformance rules remain in:

```text
product/reference/engineering/architecture-rules.md
```

This document only defines the testing approach used to verify them.

---

# 7. End-to-End Tests

## Purpose

E2E tests validate high-value journeys through realistic system boundaries.

They should exercise the product through the user-facing entry point whenever the scenario represents a user journey.

For browser-based flows:

```text
Browser
  ↓
Frontend
  ↓
Business API
  ↓
Backend
  ↓
Persistence / controlled external boundaries
```

E2E tests should remain deliberately small.

They must not replace:

- unit/domain tests;
- integration tests;
- contract tests;
- architecture tests.

## Browser E2E

Playwright is the approved browser E2E framework.

The initial browser baseline is Chromium.

Browser E2E execution should use the containerized platform foundation established by the platform Enabler.

Feature-specific E2E scenarios belong in the relevant Feature / Enabler Definition acceptance criteria.

---

# 8. AI and Probabilistic Behavior

Traditional deterministic tests are not sufficient for probabilistic AI behavior.

AI-enabled capabilities require an evaluation strategy appropriate to the capability.

## Deterministic Boundary Tests

Always test deterministic behavior around AI components normally.

Examples include:

- prompt/context assembly;
- provider routing;
- structured-output parsing;
- schema validation;
- timeout/failure behavior;
- evidence propagation;
- guardrail behavior;
- fallback handling;
- deterministic preprocessing/postprocessing.

## AI Evaluations

Material AI behavior may require evaluation dimensions such as:

- correctness;
- relevance;
- groundedness;
- evidence use;
- consistency;
- completeness;
- hallucination rate;
- classification precision/recall;
- structured-output compliance.

Exact datasets, metrics, thresholds, and acceptance criteria belong in the Feature / Enabler Definition that introduces the AI behavior.

Evaluation data should use:

- synthetic data;
- public data;
- anonymized data.

Private portfolio data must not be committed.

Changes to prompts, models, providers, retrieval strategies, or agent workflows should trigger the relevant evaluation suite when they can affect behavior.

---

# 9. Security and Resilience Testing

Testing should cover security and resilience behavior when relevant to the implemented capability.

Examples include:

## Security

- authentication;
- authorization;
- resource isolation;
- invalid/expired credentials;
- secret leakage prevention;
- input validation.

Security-critical backend behavior must not rely solely on frontend testing.

## Resilience

- provider timeout;
- provider unavailable;
- malformed external response;
- rate limiting;
- transient errors;
- database unavailable;
- broker unavailable;
- retry/idempotency behavior.

Tests should verify that failures do not corrupt authoritative business state.

---

# 10. Test Data

Test data must be:

- deterministic where applicable;
- understandable;
- minimal for the scenario;
- synthetic, anonymized, or public.

Fixtures should use realistic product concepts where useful.

Test data must not accidentally become a hidden source of product requirements.

Private user or portfolio data must not be committed.

---

# 11. Test Naming and Readability

Tests should communicate:

- scenario;
- action;
- expected result.

Examples:

```text
givenValidPortfolio_whenCreated_thenPortfolioIsPersisted
```

or:

```text
test_create_portfolio_rejects_duplicate_instrument
```

according to language conventions.

Tests must remain maintainable and readable.

A test that passes but does not clearly communicate what behavior it proves provides weak evidence.

---

# 12. Coverage

Coverage is a diagnostic signal, not the objective of testing.

The project should prefer:

```text
meaningful behavioral verification
```

over:

```text
tests written only to increase a percentage
```

Critical deterministic behavior must have sufficient automated verification to provide confidence in:

- normal scenarios;
- boundary conditions;
- failure cases;
- business invariants.

Any global or capability-specific numeric coverage gate belongs in delivery governance, not in this document.

---

# 13. Testing Responsibilities by Level

| Test Level | Primary Question |
|---|---|
| Unit / Domain | Does the deterministic behavior work correctly in isolation? |
| Integration | Does application code work correctly with real owned infrastructure? |
| Contract | Does the implementation comply with externally visible contracts? |
| Architecture | Does the code respect enforceable architecture boundaries? |
| E2E | Does a critical journey work across the complete application path? |
| AI Evaluation | Does probabilistic behavior meet the quality criteria defined for the capability? |

Use the smallest level capable of providing reliable evidence.

---

# 14. Validation Relationship

This document defines **how testing evidence is produced**.

Acceptance requirements are defined elsewhere:

```text
Feature / Enabler Definition
→ capability-specific acceptance criteria

architecture-rules.md
→ architectural acceptance criteria

governance/delivery-policy.md
→ delivery process and mandatory gates

governance/definition-of-done.md
→ completion criteria
```

A validator should combine those requirements with the evidence produced by the test levels defined here.

---

# Governing Principle

> **Testing is an evidence-producing engineering capability.  
> Governance decides which evidence is mandatory for a change to progress or be accepted.**
