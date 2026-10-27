# Platform capabilities

A capability is something the platform offers to teams and agents: a database, a cache, a queue. Each one starts as a **definition** written by a person, is **built** by an agent, is **checked** against the definition, and is **validated** by a person before it is merged.

```
Person (portal form)  ──>  capability.yaml  ──>  agent builds the rest  ──>  CI checks it  ──>  person reviews and merges
                             (the contract)       (build-platform-capability)  (TRACEABILITY.md)
```

## The definition

`capabilities/<name>/capability.yaml` follows the [definition schema](schema/capability-definition.schema.json) (`platform.starterkit.dev/v1alpha1`, `CapabilityDefinition`). It says **what**, never **how**:

| Section | Required | What it says |
|---|---|---|
| `purpose` | yes | The problem it solves, who uses it (developers, agents, the platform team) and the evidence there is demand |
| `interface` | yes | The kind people and agents request, its parameters (type, allowed values, default) and what they get back (Secret keys, status fields) |
| `guardrails` | yes | Rules `GR-n` for everyone and for agents only, each one `deny` or `approval` (a person decides); the estimated cost per day; data classification and network rules |
| `acceptance` | yes | Criteria `AC-n` in given / when / then form, checked as a person, as an agent or both |
| `implementation` | no | Hints for the agent: what to use locally and on AWS, and constraints |
| `lifecycle`, `ownership`, `delivery` | no | How long instances live, who supports it, who reviews it and its stage (`experimental` or `production`) |

The agent never edits it. Changing a capability means a new version of its definition, reviewed like a new one.

## What the agent generates

From the definition, the [build-platform-capability skill](../.claude/skills/build-platform-capability/SKILL.md) generates, in the same folder:

| File | From | What it is |
|---|---|---|
| `definition.yaml` | `interface` | Crossplane XRD, with the label `platform.starterkit.dev/capability` and annotations (title, owner, stage, guardrails, cost, outputs) that the portal and the platform MCP server read |
| `composition.yaml`, `rbac.yaml` | `implementation` | How it is built locally (Crossplane, `function-go-templating`) |
| `policy.yaml` | `guardrails` | Kyverno policies; every message starts with `[GR-n]`, and approval rules send agent requests to a person |
| `tests/kyverno/` | `guardrails` | A pass and a fail case per rule |
| `tests/e2e/test_acceptance.py` | `acceptance` | One test per criterion (`test_ac_<n>_...`), as a person (`kubectl`) and as an agent (platform MCP server) |
| `examples/` | `interface` | Requests used to render the composition |
| `docs/`, `mkdocs.yml` | everything | TechDocs in the portal |
| `SKILL.md` | `purpose`, `interface` | When and how agents should use it (linked from `.claude/skills/<name>` and from the `platform` plugin in `agent-capabilities/`) |
| `TRACEABILITY.md` | the checks | Each criterion and guardrail, the test that proves it and its result |

[`postgres-database/`](postgres-database) is the first complete example.

## The checks

```bash
make capability NAME=postgres-database   # capabilities/tools/check.sh postgres-database
```

1. **Definition and generated files** (`tools/capctl.py validate`): the definition follows the schema, the XRD matches the interface, every guardrail has a policy and policy tests, every criterion has an acceptance test.
2. **Render** every example with the composition (`crossplane render`).
3. **Policy tests** (`kyverno test`).
4. **Acceptance tests** with a cluster from `make up`: installs the capability (`tools/install.sh`) and runs `tests/e2e` as a person and as an agent. `--no-e2e` skips them.
5. **Traceability** (`tools/capctl.py trace`): writes `TRACEABILITY.md`, with a checklist for what only a person can judge.

CI runs the same on every pull request ([`.github/workflows/capabilities.yml`](../.github/workflows/capabilities.yml)): steps 1 to 3 first, then a local platform without the portal for the acceptance tests.

Tools: Python 3.12 with [`requirements.txt`](requirements.txt), the [Crossplane CLI](https://docs.crossplane.io/latest/cli/) and the [Kyverno CLI](https://kyverno.io/docs/kyverno-cli/), in the versions of [`versions.env`](../bootstrap/local/versions.env).

## How people and agents use a capability

Nothing in the portal or the MCP server is specific to a capability: both discover every XRD with the label `platform.starterkit.dev/capability`.

- **Portal:** a catalog entry with its docs, a *Create* form built from the XRD, and what each team requested, with who asked.
- **Agents:** `list_golden_paths`, `request_capability` and `get_capability_request` in the platform MCP server. A guardrail with `enforcement: approval` turns an agent request into an approval request in the **AI Platform** page.
- **kubectl:** `kubectl -n env-<environment> apply -f capabilities/<name>/examples/<example>.yaml`.

## Proposing a new one

In the portal, **Create → New platform capability**. The form has one page per section of the schema and checks the definition before submitting. It opens a pull request in the platform repository (locally, <http://localhost:3000/platform/platform-starter-kit>, seeded by `make up`) and the proposal appears in the catalog with lifecycle `proposed`. Then, on that branch, ask Claude Code: *"Build the capability in this pull request"*.
