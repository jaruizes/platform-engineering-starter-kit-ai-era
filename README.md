# Platform Engineering Starter Kit: AI Era

> A Thinnest Viable Platform in a box, built to serve **developers and AI agents with the same capabilities**.

This is the second generation of the [Platform Engineering Starter Kit](https://github.com/jaruizes/platform-eng-starter-kit). The first version showed how a platform team can provide environments to development teams through a GitOps control plane (Argo CD + Crossplane). That idea is still valid, but the context has changed: developers are no longer the only consumers of the platform. AI agents now plan, write, test and operate software too, and they need the same thing developers need: governed self-service on Golden Paths, inside guardrails.

This kit turns that idea into something you can run.

> **Status: work in progress.** This README describes the target design. The [roadmap](#roadmap) shows what is already available.

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
- **Platform MCP server**, for agents. It exposes Golden Paths as tools (`request_environment`, `create_service`…), never raw infrastructure.

### Technology choices

The kit is opinionated so it works out of the box, and modular so each piece can be replaced.

| Concern | Default | Why |
|---|---|---|
| Platform API | **Crossplane v2** (namespaced composite resources, composition functions) | The platform as a Kubernetes-style API: declarative, versioned and consumable by humans, pipelines and agents alike |
| Infrastructure as code | **OpenTofu** | Bootstraps the foundation (network, control plane cluster, identity) and can run inside compositions for modules teams already have in Terraform/OpenTofu |
| GitOps | **Argo CD** | Everything the platform provides is in Git and kept in sync |
| Portal | **Backstage** | Catalog, templates, docs and scorecards |
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
| **Database** | A PostgreSQL database (in-cluster locally, Amazon RDS on AWS) with credentials delivered as secrets | Portal · CLI · MCP |
| **Agent-ready repository** | A repository prepared to work with coding agents: `AGENTS.md`, MCP configuration and verification checks in CI | Portal · CLI |
| **LLM-powered service** | A service that consumes models through the AI gateway, with basic evaluation in CI | Portal · CLI |

Optional modules (Kafka, Redis, Vault…) can be enabled on top.

---

## The demo: "I need an environment to test this change"

The demo shows a platform working as an engineering control plane, in three acts.

1. **The developer.** From the portal, a developer creates a new service. In a couple of minutes there is a repository, a pipeline, an environment and a catalog entry, with observability. *Golden Paths, not golden cages.*
2. **The agent.** From an MCP client, a coding agent asks the platform for an environment to test a change:
   1. **Request:** the agent calls the platform MCP server.
   2. **Identify:** the platform knows which agent is asking, on behalf of which team and with which permissions.
   3. **Golden Path:** the request is resolved with the approved template, not with ad-hoc infrastructure.
   4. **Guardrails:** policies check cost, security and data rules. A second, oversized request is stopped and sent to a human for approval.
   5. **Observe:** every action is traced, measured and charged to the team's budget.
3. **The dashboard.** What was created, by whom (human or agent, for which team), how much it costs, and how delivery, developer experience and AI metrics are evolving.

*Autonomy for agents, control for the organization.*

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

```
.
├── bootstrap/          # local cluster (kind) and AWS foundation with OpenTofu
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

> Planned. The commands below describe the target experience.

### Prerequisites

- Docker, `kubectl`, `helm`, `kind`, `make`
- For AWS: an AWS account, AWS CLI with SSO or a profile, and OpenTofu
- A GitHub account

### Run it locally

```bash
make up          # local cluster + control plane + portal + Golden Paths
make demo        # load the sample organization and demo data
make demo-reset  # back to a clean state before the next demo
make down        # remove everything
```

### Run it on AWS

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

- [ ] **Demo MVP:** local setup, *new service* and *ephemeral environment* Golden Paths, platform MCP server, cost and human approval policies, first dashboard
- [ ] **Assess:** pulse check, DevEx survey and baseline scripts
- [ ] **AWS:** OpenTofu foundation, EKS and RDS compositions
- [ ] **Optimize:** agent identities, AI gateway, agent-ready and LLM-powered service Golden Paths, AI metrics dashboard
- [ ] **Run:** tests for compositions and policies, automated upgrades, SLOs, runbooks and playbook
- [ ] Other clouds as overlays

---

## Previous version

The first version of the kit is still available at [jaruizes/platform-eng-starter-kit](https://github.com/jaruizes/platform-eng-starter-kit). It is a good reference for the GitOps control plane pattern with Argo CD and Crossplane v1 on AWS.
