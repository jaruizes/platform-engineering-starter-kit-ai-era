---
name: spring-service
description: Use when the user wants a new backend service or microservice, or asks how to structure, design or change a Spring Boot service. Creates services through the platform template and keeps the code within the engineering standards.
---

# Creating and changing Spring services

This company has engineering standards that say how a service must be built:
architecture, architecture rules, technology policy, development rules and
testing. They apply to code you write exactly as to code people write. The
rules that can be checked are checked by ArchUnit in `./mvnw verify`.

## A new service

1. Do not scaffold a service by hand (no Spring Initializr, no copying another
   repository). Use the Golden Path: `create_service` in the `platform` MCP
   server. Ask the user for what you cannot infer: the name, what it does in
   the domain language, the owner team and the first functional module (a
   business capability such as `orders`, not a technical layer).
2. If you do not know the team, look for it in the catalog through the
   `portal` MCP server.
3. When it answers `created`, clone the repository it returns and read its
   `AGENTS.md`. Tell the user where the repository is and that it is in the
   catalog.

## Any change to a Spring service

1. Read the standards that matter for the change through the `portal` MCP
   server: `platform.list-engineering-standards`, then
   `platform.get-engineering-standard` (for example `architecture-rules` and
   `technology-policy`). The repository's `AGENTS.md` has the essentials.
2. Put code where the architecture says: `<module>/domain`,
   `<module>/business` and `<module>/infrastructure/...`. A new business
   capability is a new module package in the same service, not a new service.
3. Do not add a technology outside the technology policy (Kafka, Redis,
   another database...) without asking: it needs an ADR, and that is the
   user's decision.
4. Run `./mvnw verify` before you say you are done. If an architecture rule
   fails, fix the code. Never weaken, skip or delete a rule; if the rule
   really cannot be met, stop and explain the options to the user (change
   the implementation or approve an ADR).
