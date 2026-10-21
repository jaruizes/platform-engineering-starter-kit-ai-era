# Platform Engineering Starter Kit: AI Era

> A Thinnest Viable Platform in a box, built to serve **developers and AI agents with the same capabilities**.

This is the second generation of the [Platform Engineering Starter Kit](https://github.com/jaruizes/platform-eng-starter-kit). The first version showed how a platform team can provide environments to development teams through a GitOps control plane (Argo CD + Crossplane). That idea is still valid, but the context has changed: developers are no longer the only consumers of the platform. AI agents now plan, write, test and operate software too, and they need the same thing developers need: governed self-service on Golden Paths, inside guardrails.

This kit turns that idea into something you can run.

> **Status: work in progress.** The local demo works today: two Golden Paths, a developer portal (Backstage) for humans and agents, the platform MCP server, guardrails for humans and agents, human approvals and AI-era metrics. The rest of this README describes the target design; the [roadmap](#roadmap) shows what is available.

---

## Why this kit

Code is cheap, complexity is not. With AI, more people and more agents produce more software, faster. Without a platform, every team and every agent solves infrastructure, security and delivery in its own way: nobody knows what was created, by whom, or how much it costs.

Platform Engineering is still the answer, but it has to evolve:

| Platform Engineering 1.0 | Platform Engineering in the AI era |
|---|---|
| Self-service for humans | Self-service for humans **and agents** |
| Golden Paths through a portal | Golden Paths through a portal, APIs **and MCP** |
| Developer Experience (DevEx) | DevEx **and Agent Experience (AgentEx)** |
| Guardrails for developers | Guardrails for humans and agents, **as code** |
| DORA and DevEx metrics | DORA, DevEx **and AI metrics** (governance, cost, value) |

The platform becomes an **engineering control plane**: one place that decides what each consumer (human or agent) can do, and how.

## Three ways to use it

| Use | What for |
|---|---|
| **Demo** | Show, in 15–20 minutes, a platform serving a developer and an AI agent through the same Golden Paths and guardrails |
| **Assessment** | Measure where an organization is (maturity, developer experience, delivery metrics, AI usage) before building anything |
| **Accelerator** | Fork it, adapt it to your context and use it as the starting point of your own platform |

---

## Architecture

```
 Consumers        Developers & product teams   ·   Operators & SRE   ·   AI agents
                         │                             │                    │
 Interfaces         Portal (Backstage)        CLI / Platform API      Platform MCP server
                         └─────────────────────────────┼────────────────────┘
 Engineering        Golden Paths · Policy as code · Identity (humans & agents)
 control plane      AI gateway (models, quotas, cost) · Context (catalog, docs, specs)
                                                      │
 Delivery &         Argo CD (GitOps) · Crossplane v2 (platform API) · OpenTofu (IaC)
 automation         CI pipelines · security scanning
                                                      │
 Runtime &          Kubernetes (local or Amazon EKS) · AWS managed services
 infrastructure     Observability (OpenTelemetry, Prometheus, Grafana) · Cost (OpenCost)
```

Every capability is exposed through **three interfaces** backed by the same Golden Path and the same policies:

- **Portal**, for humans who want to discover and click.
- **CLI / Platform API**, for automation and for humans who prefer the terminal. The API is the set of Crossplane composite resources.
- **Platform MCP server**, for agents. It exposes Golden Paths as tools (`request_environment`, `deploy_service`…), never raw infrastructure.

### The portal in the AI era

The portal (Backstage) is no longer only for people. It is where humans and agents get **context**, while actions always go through a Golden Path:

| | Humans | AI agents |
|---|---|---|
| **Context** | Catalog: who owns what, which environments exist, who asked for them (human or agent), who approved them, what they cost, live Kubernetes status | The same catalog, live status, search and team usage, as MCP tools ([Backstage MCP actions](https://backstage.io/docs/ai/mcp-actions)), read-only |
| **Action** | Software Templates on top of the Golden Paths | The platform MCP server, with the agent identity, so the agent guardrails apply |
| **Rules** | Guardrails as code (Kyverno) | The same guardrails, plus a catalog of AI resources: the rules agents follow, the skills that teach them to use the platform, and the MCP servers they can use |
| **Decisions** | Approve or reject what agents cannot do alone, signed in with their own identity | Never: agents cannot approve their own requests |

Every request is stamped with an identity the requester cannot forge: the agent identity (platform MCP server), the portal acting on behalf of a signed-in person, or the console recording who approved what.

### Engineering standards, for humans and agents

Most organizations have documents that say how a service must be built: architecture, package structure, naming, approved technologies, testing. In the AI era they have three readers, and the kit gives each one a way in, from a single source of truth ([`standards/`](standards/), an example taken from [My-FinAI-Manager](https://github.com/jaruizes/My-FinAI-Manager/tree/main/reference/engineering)):

| | Humans | AI agents |
|---|---|---|
| **Read** | TechDocs in the portal (*Engineering standards*), one section per architecture and version | `platform.get-standards-for-entity` (which architecture and version a service follows, and what to read), `platform.get-engineering-standard` and `platform.search-engineering-standards` (filtered by architecture) in the portal MCP server, and an `AiResource` per architecture in the catalog |
| **Create** | The **Spring service** template: a repository that follows the standards from the first commit | `create_service` in the platform MCP server runs the same template; the [spring-service skill](.claude/skills/spring-service/SKILL.md) tells agents to use it instead of scaffolding by hand |
| **Change** | The repository's README | The repository's `AGENTS.md` (and `CLAUDE.md`), with the essentials and links to the full documents |
| **Check** | `./mvnw verify` locally and in CI | The same command: ArchUnit tests for the package structure, dependency direction, framework-free domain and module ownership |

Nobody has to remember the rules: the ones that can be checked are checked, the same way for human and AI-written code.

Several architectures coexist, as in any organization with some history: **backend v2** (hexagonal Spring, for new services), **backend v1** (layered Spring, deprecated but still used by older services), **Angular v1** (internal back-office) and **React v1** (customer-facing web). Each service declares its own with the label `platform.starterkit.dev/architecture` ([`standards/architectures.yaml`](standards/architectures.yaml)), so an agent changing the old orders API gets the v1 rules and one building a new service gets v2, instead of a mix of similar-looking rules from both.

![Spring service template in the portal](docs/portal-spring-template.png)

### Platform capabilities, defined by people and built by agents

New capabilities (a database, a cache, a queue) are not hand-written by the platform team any more. A person describes **what** the platform needs in a capability definition, an agent builds it, CI proves it does what the definition says, and a person validates it ([`capabilities/`](capabilities/)):

1. **Define.** In the portal, *Create → New platform capability* is a form built from the [definition schema](capabilities/schema/capability-definition.schema.json): purpose, interface, guardrails (`GR-n`, for everyone or only for agents), cost and acceptance criteria (`AC-n`, as a person, as an agent or both). It opens a pull request in the platform repository with `capabilities/<name>/capability.yaml`, and the proposal appears in the catalog.
2. **Build.** An agent, with the [build-platform-capability skill](.claude/skills/build-platform-capability/SKILL.md), generates everything from that file: Crossplane XRD and composition, Kyverno policies with their tests, an acceptance test per criterion, examples, docs and a skill for agents that will use it. It never changes the definition; when something is unclear, it asks in the pull request.
3. **Check.** `make capability NAME=<name>` (and CI) validates the definition and the generated files, renders the examples, runs the policy tests and runs the acceptance tests in the local platform, as a person and as an agent. It writes `TRACEABILITY.md`: each criterion and guardrail, the test that proves it and its result.
4. **Validate.** A person on the platform team reviews the traceability matrix and merges. The capability appears on its own in the portal (catalog entry, docs and request form) and in the platform MCP server (`request_capability`), with its guardrails enforced for both.

Changing a capability works the same way: a new version of its definition, validated by a person. The first one is a [PostgreSQL database](capabilities/postgres-database/capability.yaml).

### Technology choices

The kit is opinionated so it works out of the box, and modular so each piece can be replaced.

| Concern | Default | Why |
|---|---|---|
| Platform API | **Crossplane v2** (namespaced composite resources, composition functions) | The platform as a Kubernetes-style API: declarative, versioned and consumable by humans, pipelines and agents alike |
| Infrastructure as code | **OpenTofu** | Bootstraps the foundation (network, control plane cluster, identity) and can run inside compositions for modules teams already have in Terraform/OpenTofu |
| GitOps | **Argo CD** | Everything the platform provides is in Git and kept in sync |
| Portal | **Backstage** | Catalog, templates, AI resources (rules, skills, MCP servers) and MCP actions for agents |
| Policy as code | **Kyverno** | One policy catalog for humans and agents |
| Identity | **Keycloak** | Human users and non-human identities for agents, acting on behalf of a team |
| AI gateway | **LiteLLM** | Allowed models, quotas and cost per team |
| Observability | **OpenTelemetry, Prometheus, Grafana, OpenCost** | Includes traces of agent actions and cost per team |
| Cloud | **AWS** (Amazon EKS, RDS, IAM) | First supported cloud. Other clouds are planned as overlays |

#### How Crossplane v2 and OpenTofu work together

- **OpenTofu builds the foundation** that exists once per organization or environment: VPC, the control plane EKS cluster, IAM roles and EKS Pod Identity so no long-lived credentials are ever passed around.
- **Crossplane v2 is the platform API** that teams and agents consume: environments, services, databases. Compositions use native AWS providers and, where it makes sense, the OpenTofu provider to reuse existing modules.
- **Argo CD keeps both in sync with Git**, so every change to the platform and every request from a team is versioned and auditable.

---

## Golden Paths

| Golden Path | What you get | Interfaces |
|---|---|---|
| **New service** | Repository from a template (Java/Spring Boot, Node.js, Python), CI pipeline, deployment through GitOps, observability and catalog entry | Portal · CLI · MCP |
| **Ephemeral environment** | An isolated environment (vcluster or namespace) to test a change, with a time to live and a cost budget | Portal · CLI · MCP |
| **Database** | A PostgreSQL database (in-cluster locally, Amazon RDS on AWS) with credentials delivered as secrets. The first [platform capability](capabilities/postgres-database/) built by an agent from its definition | Portal · CLI · MCP |
| **Agent-ready repository** | A repository prepared to work with coding agents: `AGENTS.md`, MCP configuration and verification checks in CI | Portal · CLI |
| **LLM-powered service** | A service that consumes models through the AI gateway, with basic evaluation in CI | Portal · CLI |

Optional modules (Kafka, Redis, Vault…) can be enabled on top.

---

## The demo: "I need an environment to test this change"

![AI Platform page in the portal](docs/portal-ai-platform.png)

The demo shows a platform working as an engineering control plane, in three acts.

1. **The developer.** A developer asks for an environment and deploys a service through the Golden Paths in the portal, describing *what* they need, not *how*. *Golden Paths, not golden cages.*
2. **The agent.** From an MCP client, a coding agent asks the platform for an environment to test a change:
   1. **Request:** the agent reads context from the portal (who owns the service, how many environments its team has) and calls the platform MCP server.
   2. **Identify:** the platform knows which agent is asking, on behalf of which team and with which permissions.
   3. **Golden Path:** the request is resolved with the approved template, not with ad-hoc infrastructure.
   4. **Guardrails:** policies check cost, security and data rules. A second, oversized request is stopped and sent to a human, who approves it in the portal.
   5. **Observe:** every action is traced, measured and charged to the team's budget.
3. **The dashboard.** What was created, by whom (human or agent, for which team), how much it costs, and how delivery, developer experience and AI metrics are evolving, in the portal's AI Platform page and catalog.

*Autonomy for agents, control for the organization.*

The full script, with what to say in each act, is in [demo/README.md](demo/README.md).

---

## Maturity levels

The kit is organized in modules that follow four maturity levels. Each one can be used on its own.

| Level | When | What the kit provides |
|---|---|---|
| **01 · Assess** | The maturity level is low or unknown | Pulse check across five dimensions, developer experience survey, scripts to baseline delivery metrics from your Git and CI, AI usage inventory, report and roadmap templates |
| **02 · Build** | You have started, but need to get the platform off the ground | Control plane, portal, the first Golden Paths, basic policies, scorecards and the DORA + DevEx dashboard |
| **03 · Optimize** | The platform is running, but not delivering all its value yet, and it is not ready for AI | Platform MCP server, identity and guardrails for agents, human-in-the-loop approvals, AI gateway, agent-ready Golden Paths and AI metrics |
| **04 · Run** | The platform is live and has to be operated as a product | Platform SLOs, runbooks, automated upgrades, tests for compositions and policies, and the platform team playbook |

---

## Metrics

Platform Engineering 1.0 metrics are still valid. The AI era adds a new question: is the work of agents governed and creating value?

| Delivery (DORA) | Developer experience | AI & agents |
|---|---|---|
| Lead time for changes | Onboarding time to first deploy | AI-generated changes that pass guardrails the first time |
| Deployment frequency | Self-service ratio (requests without tickets) | Policy violations caught before production |
| Change failure rate | Developer satisfaction (platform NPS) | AI spend per team and cost per agent task |
| Time to restore service | Platform adoption by team | Share of agent actions going through the platform |

Measure the baseline before building anything: without it, there is no business case.

---

## Repository structure

What is available today:

```
.
├── Makefile            # up, down, demo-developer, demo-agent, demo-reset, status, capability, test
├── .mcp.json           # connects Claude Code (or any MCP client) to the platform and portal MCP servers
├── .claude/skills/     # skills that teach coding agents to use the Golden Paths and build services
├── bootstrap/local/    # k3d cluster, Crossplane, Kyverno and the platform, in one script
├── control-plane/      # Crossplane functions and permissions
├── golden-paths/
│   ├── environment/    # ephemeral environment: namespace, budget, team access, expiry, cost
│   └── app/            # new service: deployment with probes, limits, security context and service
├── policies/           # guardrails (Kyverno CEL policies) for humans and agents
├── capabilities/       # platform capabilities: definition schema, definitions, what agents generated, checks
├── mcp-server/         # platform MCP server, console and scripted demo agent (Python)
├── portal/             # Backstage: catalog, templates (Spring service included), AI Platform page and MCP actions
├── standards/          # engineering standards: TechDocs for people, AI rules for agents
├── git-server/         # local Git server (Gitea) for the repositories the templates create, and the platform repository where capabilities are proposed
├── demo/               # demo script, developer requests and reset
└── docs/
```

Target structure:

```
.
├── bootstrap/          # local cluster (k3d) and AWS foundation with OpenTofu
├── control-plane/      # Argo CD, Crossplane v2, Kyverno, Keycloak, AI gateway
├── golden-paths/       # composite resource definitions, compositions and portal templates
│   ├── service/
│   ├── ephemeral-env/
│   ├── database/
│   ├── agent-ready-repo/
│   └── llm-service/
├── portal/             # Backstage
├── mcp-server/         # platform MCP server
├── policies/           # policy catalog for humans and agents, with tests
├── observability/      # OpenTelemetry, dashboards (DORA, DevEx, AI), OpenCost
├── modules/            # optional capabilities: kafka, redis, vault...
├── assess/             # pulse check, DevEx survey, baseline scripts, report templates
├── run/                # SLOs, runbooks, platform team playbook
├── demo/               # demo script, sample organization and data, reset
└── docs/               # architecture, decisions (ADRs), how to adapt the kit
```

---

## Getting started

### Prerequisites

- Docker, [`k3d`](https://k3d.io/) 5.8+, `kubectl`, `helm` and `make`
- About 4 CPUs and 8 GB of memory for Docker. The first `make up` builds the portal image, which takes several minutes

### Run it locally

```bash
make up              # k3d cluster + Crossplane v2 + Kyverno + Golden Paths + MCP server + console + portal
make demo-developer  # act 1: a developer gets an environment and deploys a service
make demo-agent      # act 2 without an AI agent: a scripted agent uses the MCP server
make demo-reset      # back to a clean state before the next demo
make down            # remove everything
```

| What | Where |
|---|---|
| Developer portal (Backstage) | <http://localhost:7007> |
| Platform console (dashboard and approvals) | <http://localhost:8080> |
| Platform MCP server, for agents (actions) | `http://localhost:8081/mcp` |
| Portal MCP server, for agents (context, read-only) | `http://localhost:7007/api/mcp-actions/v1/context` |
| Git server with the repositories the portal creates | <http://localhost:3000> (to sign in as `platform-admin`: `kubectl -n platform-system get secret gitea-admin -o jsonpath='{.data.password}' \| base64 -d`) |
| Metrics in Prometheus format | <http://localhost:8080/metrics> |

To connect a real agent, open this folder in Claude Code: it reads [`.mcp.json`](.mcp.json) (the `platform` and `portal` servers) and the skills in [`.claude/skills/`](.claude/skills/). Then follow [the demo script](demo/README.md).

`PORTAL=false make up` skips the portal and the Git server if you only need the MCP server and the console.

> **Local demo only.** The platform MCP server has no authentication yet, the portal signs everyone in as a guest (mapped to the sample user Ana), and agents reach the portal MCP server with a fixed token. All of this is fine on a laptop and is replaced by real identity (Keycloak, and OAuth for MCP clients) in the *Optimize* milestone.

### Run it on AWS

> Planned. The commands below describe the target experience.

```bash
make aws-bootstrap   # OpenTofu: network, control plane EKS cluster, IAM, Pod Identity
make aws-up          # control plane and Golden Paths on EKS
make aws-down        # remove everything
```

No access keys are passed as arguments or stored in plain secrets: the control plane uses EKS Pod Identity.

---

## Adapting it to your organization

1. Fork the repository.
2. Choose your overlays: cloud, Git provider and identity provider.
3. Keep the Golden Paths that fit your teams, remove the rest, and build one or two with a pilot team.
4. Enable the AI modules when the platform is already in use.
5. Treat the platform as a product: discover needs, measure, get feedback, iterate.

---

## Roadmap

- [x] **Demo MVP:** local setup, *new service* and *ephemeral environment* Golden Paths, platform MCP server, cost and human approval policies, first dashboard
- [x] **Portal:** Backstage with templates on top of the same Golden Paths, live catalog of what humans and agents created, approvals, AI resources and MCP actions for agents
- [x] **Engineering standards:** TechDocs and AI rules from one source, a Spring service template with ArchUnit checks and `AGENTS.md`, and `create_service` for agents
- [x] **Platform capabilities:** a definition schema, a portal form that proposes them as pull requests, an agent skill that builds them, checks with a traceability matrix, and a PostgreSQL database as the first one
- [ ] **GitOps:** Argo CD for the platform itself
- [ ] **Assess:** pulse check, DevEx survey and baseline scripts
- [ ] **AWS:** OpenTofu foundation, EKS and RDS compositions
- [ ] **Optimize:** agent identities, AI gateway, agent-ready and LLM-powered service Golden Paths, AI metrics dashboard
- [ ] **Run:** tests for compositions and policies, automated upgrades, SLOs, runbooks and playbook
- [ ] Other clouds as overlays

---

## Previous version

The first version of the kit is still available at [jaruizes/platform-eng-starter-kit](https://github.com/jaruizes/platform-eng-starter-kit). It is a good reference for the GitOps control plane pattern with Argo CD and Crossplane v1 on AWS.
