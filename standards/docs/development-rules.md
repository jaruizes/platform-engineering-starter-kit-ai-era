# Development Rules

## Purpose

This document defines the **implementation discipline** that all code must follow.

It applies equally to:

- human-written code;
- AI-generated code;
- code produced through an SDD framework;
- remediation changes.

It does **not** redefine architecture, technology policy, testing strategy, delivery governance, or Definition of Done.

Those concerns are governed by:

```text
product/reference/engineering/architecture.md
product/reference/engineering/architecture-rules.md
product/reference/engineering/technology-policy.md
product/reference/engineering/testing-strategy.md
product/reference/governance/delivery-policy.md
product/reference/governance/definition-of-done.md
```

The governing principle is:

> **Implementation should be simple, explicit, maintainable, domain-aligned, and easy to verify.**

---

# 1. Simplicity

## DR-001 — Prefer the Simplest Correct Implementation

Implementation should use the simplest design that satisfies the approved definition, architecture, and quality requirements.

Avoid:

- speculative abstractions;
- unnecessary indirection;
- premature generalization;
- unused extension points;
- infrastructure introduced for hypothetical future needs;
- framework complexity without demonstrated value.

Do not optimize for imagined future requirements.

---

# 2. Cohesion and Responsibility

## DR-002 — Keep Units Cohesive

Classes, functions, modules, and components should have clear and cohesive responsibilities.

A unit should be split when it:

- mixes unrelated responsibilities;
- becomes difficult to understand;
- becomes difficult to test;
- coordinates concerns that belong to different boundaries.

Do not split code mechanically only to reduce file size.

---

# 3. Domain Language

## DR-003 — Preserve Product and Domain Terminology

Implementation should use the canonical terminology defined by the product model and glossary.

Do not introduce competing names for established business concepts without an explicit product-level decision.

Examples:

```text
Portfolio
Position
Financial Instrument
Market
Valuation
Analysis
Evidence
```

Names in code, APIs, tests, and persistence mappings should remain consistent with the approved domain language.

---

## DR-004 — Represent Important Domain Concepts Explicitly

Avoid primitive obsession when a value has important domain meaning or constraints.

Examples may include:

```text
Money
Currency
Percentage
Quantity
Ticker
MIC
PortfolioId
PositionId
```

The exact implementation depends on the runtime and feature, but domain meaning should not be lost unnecessarily.

Do not create value objects mechanically when a primitive remains sufficiently clear and safe.

---

# 4. Numeric Precision

## DR-005 — Use Safe Numeric Representations

Financial amounts and other precision-sensitive values must not use binary floating-point types where exact decimal behavior is required.

Use decimal-safe representations appropriate to the selected runtime.

Examples:

```text
Java   → BigDecimal
Python → Decimal
```

Rounding rules must be explicit when they affect business results.

---

# 5. Optionality and State

## DR-006 — Represent Optional and Unknown States Intentionally

Do not use null-like values ambiguously to represent different meanings.

Distinguish relevant states such as:

```text
missing
unknown
not applicable
not yet calculated
failed
unavailable
```

Where those states have different product meaning, represent them explicitly.

---

# 6. Error Handling

## DR-007 — Errors Must Be Explicit

Failures must not be silently ignored.

An error must be deliberately:

- handled;
- propagated;
- translated;
- retried;
- recorded;
- or converted into an explicit business outcome;

according to the responsibility of the current boundary.

---

## DR-008 — Do Not Leak Technical Internals

Externally visible errors must not expose:

- stack traces;
- SQL errors;
- framework exception names;
- provider responses;
- secrets;
- internal infrastructure details.

Use stable machine-readable error identifiers where required by the external contract.

---

## DR-009 — Fail Safely

When a reliable result cannot be established, prefer an explicit failure, unavailable state, or `cannot determine` outcome over fabricated or misleading information.

Do not silently replace missing data with invented defaults.

---

# 7. Configuration and Secrets

## DR-010 — Externalize Environment-Specific Configuration

Environment-dependent values must not be hard-coded into production code.

Examples include:

- endpoints;
- credentials;
- provider configuration;
- database connections;
- model identifiers;
- feature switches;
- environment-specific ports or hosts.

Use the configuration mechanism appropriate to the selected runtime.

---

## DR-011 — Secrets Must Never Be Committed

Real secrets must not appear in:

- source code;
- committed `.env` files;
- fixtures;
- examples;
- documentation;
- test data;
- scripts.

Use placeholders in committed examples.

Secret storage and delivery must follow the approved environment/security mechanism.

---

# 8. Dependencies

## DR-012 — Dependencies Must Be Intentional

Every significant dependency must have a clear purpose.

Do not add libraries:

- for trivial functionality;
- because they are familiar;
- because an AI agent prefers them;
- because they are popular;
- when the approved stack already provides the required capability.

Technology selection must comply with `technology-policy.md`.

---

## DR-013 — Remove Unused Dependencies

Unused dependencies must be removed.

They increase:

- attack surface;
- supply-chain risk;
- maintenance cost;
- build complexity;
- upgrade burden.

---

## DR-014 — Dependencies Must Respect Architecture Boundaries

A dependency must not be introduced in a package/module where it would violate `architecture-rules.md`.

Example:

```text
domain
```

must not import an infrastructure library merely because a useful helper exists there.

---

# 9. Refactoring

## DR-015 — Refactoring Must Preserve Approved Behavior

Refactoring must not silently alter product behavior.

Relevant automated tests must remain green.

If behavior must change, the change must be traceable to an approved definition or decision.

---

## DR-016 — Avoid Unrelated Refactoring During Feature Work

Feature or Enabler implementation should not include broad unrelated refactoring unless it is necessary to implement the change safely.

Large unrelated refactors should be separated into dedicated work where practical.

This rule is particularly important for AI-generated changes, where broad opportunistic edits can make review and validation harder.

---

# 10. Code Documentation

## DR-017 — Code Explains HOW; Product Definitions Explain WHAT and WHY

Do not duplicate product definitions extensively inside source code.

Product and architecture documentation remain authoritative for:

```text
what
why
constraints
decisions
```

Code, naming, and implementation comments should explain:

```text
how
non-obvious implementation trade-offs
technical constraints
```

---

## DR-018 — Comment Only When Reasoning Is Not Clear from Code

Prefer clear structure, naming, and types over explanatory comments.

Comments are appropriate when they preserve non-obvious implementation reasoning that would otherwise be lost.

Do not use comments to compensate for unnecessarily complex code.

---

# 11. Logging Discipline

## DR-019 — Logging Must Be Useful and Safe

Application logs should contain operationally useful information and relevant correlation identifiers where available.

Logs must not expose:

- passwords;
- tokens;
- API keys;
- private credentials;
- sensitive prompt contents;
- unnecessary private portfolio information.

Detailed observability requirements are defined by the architecture and observability guidance.

---

# 12. Repository Hygiene

## DR-020 — Do Not Commit Local or Generated Runtime Artifacts

Do not commit artifacts such as:

- compiled binaries;
- runtime logs;
- IDE state;
- local environments;
- temporary files;
- local test output;
- generated E2E diagnostics;
- secrets;
- machine-specific configuration.

Generated artifacts should only be committed when they are intentionally part of the project's source-of-truth model.

---

## DR-021 — Shared Test Data Must Be Safe

Shared fixtures and committed test datasets must use:

- synthetic data;
- anonymized data;
- deliberately public data.

Private portfolio information must not be committed as shared test data.

---

# 13. Generated Code and AI Changes

## DR-022 — Generated Code Is Held to the Same Engineering Standard

AI-generated code is not exempt from any implementation rule.

Generated changes must remain:

- understandable;
- maintainable;
- traceable to the approved work;
- appropriately scoped;
- consistent with surrounding code;
- free from unrelated changes.

Implementation quality is evaluated by the result, not by whether the code was written by a human or an AI.

---

## DR-023 — Do Not Preserve Generated Complexity Without Value

AI-generated abstractions, helper layers, wrappers, utilities, or configuration must be removed when they do not provide concrete value.

A generated solution should be simplified when a smaller implementation satisfies the same approved behavior and constraints.

---

# 14. Implementation Compliance

An implementation is compliant with this document when:

1. the implementation is no more complex than necessary;
2. responsibilities are cohesive;
3. canonical domain terminology is preserved;
4. precision-sensitive values use safe representations;
5. meaningful optional/error states are explicit;
6. failures are handled intentionally;
7. configuration is externalized appropriately;
8. secrets are absent from committed content;
9. dependencies are necessary and approved;
10. refactoring does not silently change behavior;
11. unrelated changes are avoided;
12. repository hygiene is preserved;
13. generated code meets the same standard as human-written code.

This document should be used together with:

```text
architecture-rules.md
technology-policy.md
testing-strategy.md
```

during automated or human validation.

---

# Governing Principle

> **Architecture defines the permitted structure.  
> Technology policy defines the permitted stack.  
> Testing strategy defines the required evidence.  
> Development rules define the discipline of the implementation itself.**
