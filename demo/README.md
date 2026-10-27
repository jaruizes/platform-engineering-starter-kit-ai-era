# Demo: "I need an environment to test this change"

A 15–20 minute demo of a platform working as an **engineering control plane**: a developer and an AI agent consume the same Golden Paths, inside the same guardrails, and everything is traced and measured.

![AI Platform page in the portal](../docs/portal-ai-platform.png)

## Before the demo

```bash
make up            # once: creates the local platform (takes a few minutes)
make demo-reset    # before every demo: clean state
```

Open the portal at <http://localhost:7007>, click **Enter** (you are Ana, from the platform team) and keep it visible during the whole demo. The lighter console at <http://localhost:8080> shows the same approvals and metrics.

To use a real coding agent, connect it to the two MCP servers: `platform` (`http://localhost:8081/mcp`) to act, and `portal` (`http://localhost:7007/api/mcp-actions/v1/context`, with the header `Authorization: Bearer platform-starter-kit-local-demo`) to read context. This repository already includes a `.mcp.json` and two skills ([platform Golden Paths](../.claude/skills/platform-golden-paths/SKILL.md) and [Spring services](../.claude/skills/spring-service/SKILL.md)), so [Claude Code](https://claude.com/claude-code) opened in this folder offers both servers and knows how to use the platform. For any other agent:

```bash
claude mcp add --transport http platform http://localhost:8081/mcp
claude mcp add --transport http portal http://localhost:7007/api/mcp-actions/v1/context \
  --header "Authorization: Bearer platform-starter-kit-local-demo"
```

No agent at hand, or no network? `make demo-agent` runs a scripted agent that makes the same calls.

## Act 1: the developer (Platform Engineering 1.0)

*Message: Golden Paths, not golden cages. The developer asks for what they need, the platform takes care of how.*

In the portal:

1. **Create → Ephemeral environment.** Name `payments-dev`, team *Payments*, a purpose, size *medium*, 48 hours. The developer only says team, purpose, size and how long. No namespaces, quotas, permissions or cost labels.
2. Open the environment in the catalog: it is ready in seconds, with a CPU and memory budget, access for the team and an expiry date. The **Golden Path request** card shows it was requested by a **human** (Ana), and what it costs.
3. **Create → New service.** Environment `payments-dev`, name `refunds-api`. The Golden Path adds health probes, resource limits, a hardened security context and ownership labels. The **Kubernetes** tab of the service shows its pods.

Prefer the terminal? `make demo-developer` does the same through the platform API: show [`demo/developer/environment.yaml`](developer/environment.yaml) and [`demo/developer/service.yaml`](developer/service.yaml).

## Act 2: the agent (Platform Engineering in the AI era)

*Message: an agent consumes the platform the same way a developer does: through a governed interface, on a Golden Path, inside the guardrails.*

Ask the agent, in plain language:

1. **"Which Golden Paths does our platform offer?"**
   The agent discovers them through MCP, with their parameters and guardrails.
2. **"I need an environment to test the new discount rules for the checkout team, and deploy the checkout service there."**
   - *Context:* the agent asks the portal how many environments the checkout team has and what they cost, before asking for a new one.
   - *Request:* the agent calls the platform MCP server.
   - *Identify:* the platform knows it is an agent, which one, and for which team (see the console).
   - *Golden Path:* the same template the developer used, not ad-hoc infrastructure.
   - *Observe:* the environment and the service appear in the portal catalog, tagged as requested by an agent, charged to the checkout team.
3. **"Now I need a large environment for a load test, for 24 hours."**
   - *Guardrails:* the policy stops it. Agents only get small environments on their own.
   - The request goes to a human: it appears in the portal's **AI Platform** page under **Agent requests waiting for a human decision**. The agent tells the user and gives the approval id.
   - Approve it in the portal. You do not type your name: the portal knows who you are. The environment is created with the agent as requester and Ana as approver.
4. **"And one that stays for two weeks."**
   - Stopped by the cost guardrail that applies to everyone, humans included: environments live at most 72 hours. Approval cannot bypass it.

5. **"Implement the spec demo/example/specs/loyalty-points.md and deploy it in that environment."**
   - *Golden Path:* the agent calls `create_service` with the environment: a repository from the Spring service template, with its pipeline and its `deploy/` folder (the `App` and its PostgreSQL database).
   - *Delivery:* the agent implements the spec and pushes to `main`. The pipeline (Gitea Actions) runs the tests and the architecture rules, builds the image with Jib and writes it into `deploy/app.yaml`; Argo CD applies `deploy/` to the environment ([localhost:8082](http://localhost:8082)).
   - *Guardrails:* Argo CD deploys with its own identity, but the platform still knows the agent asked for it, so the agent guardrails apply too.
   - *Observe:* the agent follows `get_service_status` (pipeline, Argo CD and pods, with the logs if it does not start) until it is ready, and gives you the `kubectl port-forward` and `curl` to try it.
   - *Team roles:* with the `dev-team` plugin installed ([agent capabilities](../agent-capabilities/README.md)), use `/dev-team:implement-spec demo/example/specs/loyalty-points.md` instead: it reviews the spec first, the QA engineer writes a test per acceptance criterion, the backend developer implements it and the architect reviews it before the push. `/dev-team:review-spec` alone shows the review on a spec with mistakes.

With the scripted agent, `make demo-agent` runs steps 1 to 4 in one go; then approve the load test in the portal.

**The contrast to tell:** without a platform, the agent writes its own infrastructure code, with its own credentials, outside any standard. Nobody knows what was created, by whom, or how much it costs.

## Act 3: the numbers

*Message: Platform Engineering 1.0 metrics are still valid. The AI era adds a new question: is the work of agents governed and creating value?*

In the portal's **AI Platform** page:

- Share of environments requested by agents.
- Agent requests that passed the guardrails the first time, and the ones caught by policy.
- Requests waiting for a human, and who approved what.
- Estimated cost per day, per team, and the part that comes from agents.

The same numbers are available in Prometheus format at <http://localhost:8080/metrics>.

And in the catalog, filter by kind **AiResource**: the rules agents follow (each one linked to the policy that enforces it) and the skill that teaches them to use the platform. Under **APIs**, the two MCP servers agents can use. Governance of AI is part of the catalog, like any other software.

**Closing line:** *autonomy for agents, control for the organization.*

## Act 4: the engineering standards (optional, 8 minutes)

*Message: the organization's architecture rules have three readers now: people, agents and CI. One source of truth, and the rules that can be checked are checked.*

1. **Docs → Engineering standards.** Four architectures side by side (backend v2 and the deprecated v1, Angular and React), each with its architecture, rules and examples, plus the documents for all of them (technology policy, development rules, testing), as TechDocs. This is where people read them.
2. **Create → Spring service.** Name `payments-service`, a description, owner *Payments*, first module `payments`. The repository appears in the Git server (<http://localhost:3000/platform/payments-service>) and in the catalog a few seconds later. Show its package structure (`payments/domain`, `business`, `infrastructure`), its `AGENTS.md` and `src/test/java/**/architecture/ArchitectureTest.java`.
3. Ask the agent: **"Create a new service for the checkout team that manages gift cards."** With the Spring service skill, it does not scaffold by hand: it calls `create_service`, the same template, and the catalog shows the service as requested by the agent. Then: **"Which rules must I follow to add a REST endpoint?"** It reads them through the portal MCP server (`platform.get-standards-for-entity` and `platform.get-engineering-standard`).
4. Ask the agent: **"Add a refund endpoint to the orders API."** The orders API is an older service: `get-standards-for-entity` says it follows **backend v1 (layered, deprecated)**, so the agent works with controller, service and repository layers and cites `BL-` rules, instead of applying the hexagonal v2 rules it would use for a new service. Then: **"How should the storefront validate the checkout form?"** It searches only the **React v1** standards (`search-engineering-standards` with `architecture: frontend-react-v1`), not the Angular ones. In the catalog, filter by the tag `architecture` to see the four architectures, and open a service to see which one it depends on.
5. Break a rule on purpose: in the cloned repository, make a class in `domain` use a JPA annotation and run `./mvnw verify`. ArchUnit fails and names the rule (AAC-003). The same happens for code written by an agent.

The standards are an example taken from [My-FinAI-Manager](https://github.com/jaruizes/My-FinAI-Manager/tree/main/reference/engineering); replace [`standards/`](../standards) with your own.

## Act 5: a new platform capability (optional, 10 minutes)

*Message: the platform team describes what the platform needs; an agent builds it; checks prove it; a person decides. The definition is the contract.*

1. **Catalog → PostgreSQL database.** A capability built this way. Show its **TechDocs** (what you get, guardrails, cost) and [its definition](../capabilities/postgres-database/capability.yaml): purpose, interface, guardrails `GR-1..3` and acceptance criteria `AC-1..6`. Then [`TRACEABILITY.md`](../capabilities/postgres-database/TRACEABILITY.md): each criterion and guardrail, the test that proves it, and its result.
2. **Create → PostgreSQL database** in `payments-dev`. It is ready in a couple of minutes with a Secret to connect to it. Ask the agent: **"I need a large database in payments-dev to test the migration."** GR-3 sends it to a human, in the **AI Platform** page, like the large environment in Act 2.
3. **Create → New platform capability.** Fill in a Redis cache: a parameter `size`, a guardrail for everyone (only in `env-*` namespaces) and one for agents (only small), a cost per size and an acceptance criterion. The form checks the definition against the schema. It opens a pull request in the platform repository (<http://localhost:3000/platform/platform-starter-kit/pulls>) and the proposal appears in the catalog with lifecycle *proposed*.
4. Build it: check out the pull request branch and ask Claude Code **"Build the capability in this pull request"**. The [build-platform-capability skill](../.claude/skills/build-platform-capability/SKILL.md) generates the composition, policies and tests, and runs `make capability NAME=redis-cache` until it passes. A person reviews `TRACEABILITY.md` and merges.

The checks run with `make capability NAME=<name>` and in CI ([`.github/workflows/capabilities.yml`](../.github/workflows/capabilities.yml)). How the definition, the generated files and the checks fit together is in [`capabilities/README.md`](../capabilities/README.md).

## What is under the hood

| Step | How it works |
|---|---|
| Golden Paths | Crossplane v2 composite resources: [`Environment`](../golden-paths/environment) and [`App`](../golden-paths/app) |
| Identify | Kyverno [`identify-requester`](../policies/10-identify-requester.yaml) stamps the authenticated requester and whether it is a human or an agent |
| Guardrails | Kyverno [`cost-guardrails`](../policies/20-cost-guardrails.yaml) (for everyone) and [`agent-guardrails`](../policies/30-agent-guardrails.yaml) (for agents) |
| Portal | Backstage: [Software Templates](../portal/catalog/templates) that call the Golden Paths on behalf of the signed-in person, a [catalog provider](../portal/plugins/platform-backend/src/catalog.ts) that brings environments and services from the cluster, and MCP actions for agents |
| Engineering standards | [`standards/`](../standards): four architectures with their versions ([`architectures.yaml`](../standards/architectures.yaml)), TechDocs built into the portal image, an `AiResource` per architecture, sample services on each one ([`portal/catalog/services.yaml`](../portal/catalog/services.yaml)), and MCP actions that tell agents which rules apply to a service, serve the Markdown and search it by architecture |
| Spring service | A [template](../portal/catalog/templates/spring-service) that publishes to the local Git server ([Gitea](../git-server/gitea.yaml)); the catalog discovers every repository of the `platform` organization. `create_service` in the platform MCP server runs the same template with a token that only reaches the scaffolder and the catalog |
| Delivery | Each service repository has a pipeline ([Gitea Actions](../portal/catalog/templates/spring-service/skeleton/.gitea/workflows/deliver.yaml), run by a [runner](../delivery/runner) in the cluster) that builds the image with Jib, pushes it to the [service image registry](../delivery/registry.yaml) (ECR on AWS) and commits it into `deploy/`. An [Argo CD ApplicationSet](../delivery/argocd/services.yaml) deploys the `deploy/` folder of every repository; [`identify-requester`](../policies/10-identify-requester.yaml) records who created the service, so the guardrails still apply |
| Agent capabilities | A [marketplace of Claude Code plugins](../agent-capabilities/README.md) for every team: `platform` (MCP servers, skills and a hook that keeps infrastructure on the Golden Paths) and `dev-team` (backend, frontend, QA and architect subagents, `review-spec` and `implement-spec`). Service repositories offer them when opened |
| Human in the loop | The console creates approved requests with its own identity and records the approver; the portal passes on who is signed in. [`protect-audit-trail`](../policies/30-agent-guardrails.yaml) stops anyone else from doing so |
| Platform capabilities | [`capabilities/`](../capabilities): a definition per capability, what the agent generated from it (XRD, composition, policies, tests) and the checks; the portal and the platform MCP server discover them from the label `platform.starterkit.dev/capability` on the XRD |
| Time to live | Kyverno deletes environments when their time to live is over |
| Observe | Every action is a Kubernetes event in `platform-system`; the console reads events and resources |

## Troubleshooting

- **The portal shows the sign-in page again:** click **Enter**; the demo keeps no session state.
- **The console is empty:** run `make status`. If Golden Path resources are missing, run `make up` again; it is idempotent.
- **"Team already has 3 active environments":** that is the team budget guardrail. Run `make demo-reset`.
- **A new capability is not in the portal:** the portal reads capabilities from the cluster every 15 seconds; check `make capabilities`. A proposal is read from the open pull requests of the platform repository.
- **The Spring service does not appear in the catalog:** it is discovered from the Git server every 15 seconds. Check the repository exists at <http://localhost:3000/platform>.
- **"The repository with the same name already exists":** pick another name, or run `make demo-reset`, which also deletes the repositories created from templates.
- **The agent does not see the `platform` or `portal` server:** check <http://localhost:8081/healthz> answers `ok` and the portal opens, then restart the agent.
