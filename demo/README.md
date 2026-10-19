# Demo: "I need an environment to test this change"

A 15–20 minute demo of a platform working as an **engineering control plane**: a developer and an AI agent consume the same Golden Paths, inside the same guardrails, and everything is traced and measured.

![Platform console](../docs/console.png)

## Before the demo

```bash
make up            # once: creates the local platform (takes a few minutes)
make demo-reset    # before every demo: clean state
```

Open the console at <http://localhost:8080> and keep it visible during the whole demo.

To use a real coding agent, connect it to the platform MCP server at `http://localhost:8081/mcp`. This repository already includes a `.mcp.json`, so [Claude Code](https://claude.com/claude-code) opened in this folder offers the `platform` server. For any other agent:

```bash
claude mcp add --transport http platform http://localhost:8081/mcp
```

No agent at hand, or no network? `make demo-agent` runs a scripted agent that makes the same calls.

## Act 1: the developer (Platform Engineering 1.0)

*Message: Golden Paths, not golden cages. The developer asks for what they need, the platform takes care of how.*

```bash
make demo-developer
```

1. Show [`demo/developer/environment.yaml`](developer/environment.yaml): the developer only says team, purpose, size and how long. No namespaces, quotas, permissions or cost labels.
2. The environment is ready in seconds, with a CPU and memory budget, access for the team, and an expiry date.
3. Show [`demo/developer/service.yaml`](developer/service.yaml): four lines. The Golden Path adds health probes, resource limits, a hardened security context and ownership labels.
4. In the console: the environment appears as requested by a **human**, with its estimated cost.

## Act 2: the agent (Platform Engineering in the AI era)

*Message: an agent consumes the platform the same way a developer does: through a governed interface, on a Golden Path, inside the guardrails.*

Ask the agent, in plain language:

1. **"Which Golden Paths does our platform offer?"**
   The agent discovers them through MCP, with their parameters and guardrails.
2. **"I need an environment to test the new discount rules for the checkout team, and deploy the checkout service there."**
   - *Request:* the agent calls the platform MCP server.
   - *Identify:* the platform knows it is an agent, which one, and for which team (see the console).
   - *Golden Path:* the same template the developer used, not ad-hoc infrastructure.
   - *Observe:* the environment, the service and the activity appear in the console, charged to the checkout team.
3. **"Now I need a large environment for a load test, for 24 hours."**
   - *Guardrails:* the policy stops it. Agents only get small environments on their own.
   - The request goes to a human: it appears in the console under **Waiting for a human decision**. The agent tells the user and gives the approval id.
   - Approve it in the console. The environment is created with the agent as requester and you as approver.
4. **"And one that stays for two weeks."**
   - Stopped by the cost guardrail that applies to everyone, humans included: environments live at most 72 hours. Approval cannot bypass it.

With the scripted agent, `make demo-agent` runs steps 1 to 4 in one go; then approve the load test in the console.

**The contrast to tell:** without a platform, the agent writes its own infrastructure code, with its own credentials, outside any standard. Nobody knows what was created, by whom, or how much it costs.

## Act 3: the numbers

*Message: Platform Engineering 1.0 metrics are still valid. The AI era adds a new question: is the work of agents governed and creating value?*

In the console:

- Share of environments requested by agents.
- Agent requests that passed the guardrails the first time, and the ones caught by policy.
- Requests waiting for a human, and who approved what.
- Estimated cost per day, per team, and the part that comes from agents.

The same numbers are available in Prometheus format at <http://localhost:8080/metrics>.

**Closing line:** *autonomy for agents, control for the organization.*

## What is under the hood

| Step | How it works |
|---|---|
| Golden Paths | Crossplane v2 composite resources: [`Environment`](../golden-paths/environment) and [`App`](../golden-paths/app) |
| Identify | Kyverno [`identify-requester`](../policies/10-identify-requester.yaml) stamps the authenticated requester and whether it is a human or an agent |
| Guardrails | Kyverno [`cost-guardrails`](../policies/20-cost-guardrails.yaml) (for everyone) and [`agent-guardrails`](../policies/30-agent-guardrails.yaml) (for agents) |
| Human in the loop | The console creates approved requests with its own identity and records the approver; [`protect-audit-trail`](../policies/30-agent-guardrails.yaml) stops anyone else from doing so |
| Time to live | Kyverno deletes environments when their time to live is over |
| Observe | Every action is a Kubernetes event in `platform-system`; the console reads events and resources |

## Troubleshooting

- **The console is empty:** run `make status`. If Golden Path resources are missing, run `make up` again; it is idempotent.
- **"Team already has 3 active environments":** that is the team budget guardrail. Run `make demo-reset`.
- **The agent does not see the `platform` server:** check <http://localhost:8081/healthz> answers `ok`, then restart the agent.
