---
name: build-platform-capability
description: Use when a platform engineer asks you to build, implement or update a platform capability from a CapabilityDefinition (capabilities/<name>/capability.yaml), usually from a "New platform capability" pull request opened by the developer portal.
---

# Building a platform capability from its definition

A platform engineer wrote `capabilities/<name>/capability.yaml`: **what** the
capability is (interface), **its limits** (guardrails) and **how to know it
works** (acceptance criteria). You decide **how** to build it. A person on
the platform team validates your work against the definition before it is
merged. Your job is to make that validation easy: every file you write must
trace back to a line of the definition.

## Rules

- Never edit `capability.yaml`. If something is ambiguous or contradictory
  (a criterion that clashes with a guardrail, a parameter with no clear
  meaning), stop and ask in the pull request, or ask the user. Do not guess.
  The engineer answers by changing the definition.
- Never weaken a test, a policy or a check to get to green. If a criterion
  cannot be met, explain why in the pull request.
- Build only what the definition asks for. No extra parameters, outputs or
  features: the interface is a contract.
- Follow the engineering standards (portal MCP server:
  `platform.get-engineering-standard`, at least `technology-policy`) and the
  implementation constraints in the definition.

## Steps

1. **Get the definition.** It is usually on a branch `capability/<name>-...` of
   the platform repository, opened as a pull request by the portal. Check it
   out and read `capabilities/<name>/capability.yaml` completely. Run
   `python capabilities/tools/capctl.py validate <name> --definition-only`.
2. **Learn from what exists.** `capabilities/postgres-database/` is a
   complete example; `golden-paths/` shows the composition style used here.
3. **Generate the files** in `capabilities/<name>/`:

   | From | Generate |
   |---|---|
   | `interface` | `definition.yaml`: the Crossplane XRD (group `platform.starterkit.dev`, version `v1alpha1`, exactly the parameters, types, allowed values and defaults of the interface; the outputs in `status`). |
   | `interface`, `guardrails`, `metadata` | On the XRD: the label `platform.starterkit.dev/capability: <name>` and the annotations `platform.starterkit.dev/{title,owner,stage,description,guardrails,examples,cost,outputs}` copied from the definition (lists and maps as JSON). The portal and the platform MCP server read them: that is how the capability appears for people and agents without changing either. |
   | `implementation` | `composition.yaml`: a Crossplane Composition (Pipeline mode, `function-go-templating`) for the local platform. If it composes kinds Crossplane cannot manage yet, add `rbac.yaml` with a ClusterRole labelled `rbac.crossplane.io/aggregate-to-crossplane: "true"`. Write the estimated cost per day in `status.estimatedDailyCost` when the definition has a cost model. |
   | `interface` | `examples/*.yaml`: at least one request per meaningful combination; used to render the composition. |
   | `guardrails` | `policy.yaml`: Kyverno `ValidatingPolicy` resources. Every message starts with the rule id, `[GR-n] ...`. A rule with `enforcement: approval` says `Human approval required:` right after the id; the platform MCP server turns those rejections into approval requests for a person. Agent rules match `request.userInfo.username == 'system:serviceaccount:platform-system:platform-mcp'`. |
   | `guardrails` | `tests/kyverno/kyverno-test.yaml` and its resources: at least one pass and one fail case per rule, with the rule id in the test or resource names. |
   | `acceptance` | `tests/e2e/test_acceptance.py`: one pytest test per criterion, named `test_ac_<n>_<what>`. A criterion checked `as: both` is parametrized with the `requester` fixture so it runs as a human and as an agent. Use the helpers in `capabilities/tools/e2e.py`. |
   | `purpose`, `interface`, `lifecycle`, `ownership` | `docs/index.md` and `mkdocs.yml` (TechDocs): what it is for, how to request it (portal, kubectl, MCP), what you get, the guardrails, cost and lifecycle. |
   | `purpose`, `interface.examples` | `SKILL.md`: when an agent should use the capability and how (`request_capability` in the platform MCP server), and when not to. Link it so coding agents find it: `ln -s ../../capabilities/<name> .claude/skills/<name>`. |

4. **Check it** with `make capability NAME=<name>` (`capabilities/tools/check.sh <name>`). It runs what CI
   runs: the definition and the generated files against each other
   (`capctl validate`), `crossplane render` of every example, `kyverno test`,
   and, with a cluster from `make up`, installs the capability and runs the
   acceptance tests as a human and as an agent. It writes `TRACEABILITY.md`.
   Iterate until it is green.
5. **Hand it over.** Commit on the same branch and push. Comment on the pull
   request with a short summary, anything you had to interpret, and point the
   reviewer to `TRACEABILITY.md`. Do not merge: a person validates it.
