---
name: engineering-standards
description: Use before designing, writing or reviewing code for any service or application of this organization (backend or frontend), or when asked how something must be built here. Finds the architecture and version that apply and reads its rules.
---

# Following the engineering standards

Several architectures coexist here, and some in more than one version:
backend v2 (hexagonal Spring, for new services), backend v1 (layered Spring,
deprecated, still used by older services), Angular v1 (internal back-office)
and React v1 (customer-facing web). Their rules look alike but differ. Using
the rules of the wrong one is the most common mistake: always find out which
one applies first.

Everything is in the `portal` MCP server.

## Changing an existing service or application

1. Find it in the catalog (`catalog.query-catalog-entities`) if you do not
   know its entity ref.
2. Call `platform.get-standards-for-entity` with it. It returns its
   architecture, version and lifecycle, a warning if it is deprecated, and
   the documents to read, in order.
3. Read at least its `architecture-rules` and the common documents that
   matter for the change with `platform.get-engineering-standard`. Read its
   `examples` when you are unsure what compliant code looks like.
4. For a specific question (error handling, forms, transactions...), use
   `platform.search-engineering-standards` **with the architecture** of the
   service, so rules from another version do not mix in. Read the whole
   document when a result matters.
5. If the architecture is deprecated, follow its rules for this change. Do
   not start migrating it to the new version unless the user asks: that is a
   planned change with its own decision.
6. If the service declares no architecture, ask the user which one it
   follows instead of guessing from the code.

## Building something new

1. `platform.list-engineering-standards` lists the architectures with what
   each one is for. Pick the one whose `useFor` fits, never a deprecated one,
   and tell the user which one and why.
2. If it has a template (`template` in the list, for example the Spring
   service template), create it through the platform, not by hand: for
   Spring services, follow the `spring-service` skill.

## Always

- Cite the rule ids (`AAC-003`, `BL-004`, `FA-007`, `FR-012`...) when you
  explain a design decision or a review finding.
- The rules that can be checked are checked in CI (ArchUnit, ESLint
  boundaries, budgets). Never weaken a check to get to green: fix the code or
  explain the options to the user.
