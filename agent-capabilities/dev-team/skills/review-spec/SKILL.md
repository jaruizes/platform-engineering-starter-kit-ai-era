---
name: review-spec
description: Use when the user shares a functional spec of a service or feature, asks whether a spec is ready, or before implementing one. Checks that it is complete, consistent and testable, and proposes concrete wording for each problem.
---

# Reviewing a spec before building it

A spec with a contradiction gets implemented with a guess. Finding it before
writing code is cheaper than finding it in the demo. Review the spec, report,
and let the user decide; do not change the spec unless they ask.

[spec-template.md](spec-template.md) is the structure a spec on this platform
follows. Use it to check the spec, and to help the user write a new one.

## What to check

1. **Identity.** Name (lowercase and dashes, it becomes the repository), owner
   team, architecture and first functional module. The architecture must be
   one of `platform.list-engineering-standards` in the portal MCP server and
   not deprecated for a new service ("Backend v2" is `backend-spring-v2`).
   Check the team exists in the catalog.
2. **API.** Every endpoint has its method, path, input, output with an
   example, and what it answers when something is wrong (not found, invalid
   input). Paths and names use the domain language.
3. **Business rules.** Ranges cover every value once: no gaps, no overlaps,
   and each boundary belongs to exactly one range. Units and currencies are
   explicit. Time references are unambiguous ("current calendar year" versus
   "last 12 months").
4. **Acceptance criteria.** Each one is testable, follows from a rule, and
   agrees with the rules and with the other criteria, boundaries included.
   Every rule has at least one criterion. Look for criteria copied from
   another spec that do not apply.
5. **Data and dependencies.** Test data covers each criterion. Every other
   service it calls is named with its contract, or the spec says it is
   simulated.
6. **Platform fit.** Anything outside the technology policy (a broker, a
   cache, another database) needs an ADR. Anything about where it runs
   (environment size, time to live) must fit the guardrails, or it will need
   a human approval.

## How to report

A short table, most important first:

| # | Severity | Where | Problem | Proposed wording |
|---|---|---|---|---|

- **Blocking**: two readings give different behavior (a contradiction, an
  overlap, a boundary assigned twice). Do not implement until the user
  chooses.
- **Should fix**: missing information you can assume safely; say what you
  would assume.
- **Note**: wording, typos, style.

End with one line: "Ready to implement", or "Ready once the blocking items are
decided".
