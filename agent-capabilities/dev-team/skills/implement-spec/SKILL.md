---
name: implement-spec
description: Use when the user asks to implement a spec, a feature description or a user story of a service end to end. Reviews the spec, creates or changes the service through the platform, writes the tests from the acceptance criteria, deploys it to a test environment and tells the user how to try it.
---

# Implementing a spec end to end

The goal is not code in a repository: it is a service the user can call,
that does what the spec says, built the way the company builds services.
The `platform` plugin's skills say how to use the platform and the
standards; this skill says in which order, and which role of the team does
each step. When the subagents of this plugin are available, delegate to them
as indicated; otherwise do the step yourself with the same instructions.

## 1. Review the spec

Follow the `review-spec` skill. If there are blocking items, show them to the
user with your proposed wording and wait for their decision. For the rest,
state what you assume and go on.

## 2. Find the context

- **Team**: from the spec, or the owner of the service in the catalog
  (portal MCP server).
- **Architecture**: from the spec, or from the service if it exists
  (`platform.get-standards-for-entity`). A new service never uses a
  deprecated architecture.
- **New or existing service**: look it up in the catalog. If it exists,
  clone it and change it; do not create a second one.

## 3. Get somewhere to run it

Unless the user says otherwise, the service is delivered to a test
environment so they can try it. Check the team first (`platform.get-team-usage`):
reuse one of its ready environments, or request a small one for 8 hours
(`request_environment`). Follow the `platform-golden-paths` skill if a
guardrail answers.

## 4. Create the service

For a new service, follow the `spring-service` skill: `create_service` with the
name, description, team, module, base package and the environment. Clone the
repository it returns and read its `AGENTS.md`.

## 5. Build it

1. **Contract**: the API of the spec in `contracts/openapi.yaml`.
2. **Tests first** (`qa-engineer`): one test per acceptance criterion, plus the
   boundaries, using the spec's test data.
3. **Implementation** (`backend-developer` or `frontend-developer`): until the
   tests and `./mvnw verify` pass, without touching what the tests check.
4. **Review** (`architect`): against the architecture rules and the technology
   policy. Fix what it marks as required, then verify again.

Simulated dependencies and in-memory test data live behind a port in the
domain, with an adapter in `infrastructure`, so the real one can replace them
later without touching the business logic.

## 6. Deliver it

Commit with a message that names the spec, and push to `main`: the pipeline
builds the image and Argo CD deploys it. Follow it with `get_service_status`
until it is `ready`. If it fails, read what it returns (the failed pipeline
step or the logs), fix it and push again.

## 7. Tell the user

- What was built: endpoints and modules.
- The acceptance criteria and the test that covers each one.
- Where it runs: environment, team and when it expires.
- How to try it: the `kubectl port-forward` that `get_service_status`
  returns, and one `curl` per endpoint with the spec's test data and the
  answer to expect.
- What you assumed, and what is left out.
