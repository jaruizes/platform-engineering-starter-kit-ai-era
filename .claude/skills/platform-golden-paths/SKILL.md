---
name: platform-golden-paths
description: Use when the user needs an environment, wants to deploy or test a service, or asks about environments, costs or approvals on the internal platform. Gets them through the platform Golden Paths instead of writing infrastructure code.
---

# Using the platform Golden Paths

This company has an Internal Developer Platform. Do not write Terraform,
Kubernetes manifests or cloud CLI commands to get infrastructure. Use the
platform, through its two MCP servers:

- `portal` (the developer portal, read-only) gives context: the catalog, who
  owns what, which environments a team has, live status and pending approvals.
- `platform` (the platform MCP server) acts: it requests environments and
  deploys services through the Golden Paths, with your agent identity.

## Steps

1. Find the team. If the user did not say, look for the service in the catalog
   (`catalog.query-catalog-entities` or `catalog.get-catalog-entity`) and use
   its owner.
2. Check the team before asking for anything: `platform.get-team-usage` tells
   you its environments, its daily cost and how many environment slots are
   free (at most 3 per team). If there are none free, tell the user which
   environments exist instead of trying.
3. Request what is needed with `request_environment` (small by default, a time
   to live that fits the task, at most 72 hours) and then `deploy_service`.
4. If the answer is `pending_approval`, a guardrail sent it to a human. Tell
   the user, give them the approval id, and say it can be approved in the
   portal's AI Platform page. Offer a small environment if that is enough.
   Never try to approve it yourself.
5. If the answer is `denied`, explain the guardrail in one sentence and
   propose a request that fits it.
6. When the work is done, offer to delete the environment with
   `delete_environment` to free the team's budget.

## Guardrails you will meet

- Agents can only get small environments on their own.
- Environments live at most 72 hours, and each team has at most 3.
- Agents only deploy into ephemeral environments (`env-*` namespaces).
- Every request records that it came from an agent, and which one.
