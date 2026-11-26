# Agent clients, one platform

`skills/` contains the canonical skills. `instructions/AGENTS.md` is shared repository guidance. `clients/` contains only the transport configuration adapters; no platform code is copied here.

| Client | MCP configuration | Skill discovery | Instructions |
|---|---|---|---|
| Claude Code | `.mcp.json` → `clients/claude-code/mcp.json` | `.claude/skills` → `platform/ai/agent-tooling/skills` | `CLAUDE.md` imports shared guidance |
| Codex | `.codex/config.toml` → `clients/codex/config.toml` | `.platform/ai/agent-tooling/skills` → `platform/ai/agent-tooling/skills` | `AGENTS.md` links shared guidance |
| Gemini CLI | `.gemini/settings.json` → `clients/gemini-cli/settings.json` | `.gemini/skills` → `platform/ai/agent-tooling/skills` | `GEMINI.md` imports shared guidance |

Run `make up`, then open the repository with your client. Review the project trust/MCP prompts and verify both `platform` and `portal` servers in the client's MCP listing. All three clients connect to the existing Streamable HTTP services; changing clients does not install a second platform. The checked-in headers are for the local demo only. For AWS, use the public URLs printed by `make aws-up` and the deployment's tokens; keep real credentials outside version control. Codex project config is loaded only for trusted projects.

The platform server handles actions; the portal server supplies context and engineering standards. Identity, policies and approvals remain server responsibilities. A config adapter prepares compatibility; live interoperability still needs each CLI and a running platform.

For new capability skills, create `platform/ai/agent-tooling/skills/<name>/SKILL.md` and link `platform/capabilities/infrastructure/<name>/SKILL.md` to it with `../../../ai/agent-tooling/skills/<name>/SKILL.md`. The client skill directory links expose it automatically.

Configuration references: [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Codex MCP](https://developers.openai.com/codex/mcp), [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/).

## REST-to-MCP Zero-UI Golden Path

The `api-to-mcp` skill complements Spring/Angular generation:
create a deployed Spring REST service first; then use the platform MCP
`create_api_mcp_adapter` tool. Edit the new repository's approved
`operations.json` and push to main to deploy a **remote Streamable HTTP MCP** server in the
same ephemeral namespace as the backend. Each person opens their own
Kubernetes port-forward and registers it in Claude Code with `--scope user`,
so it can be used from any folder. Local stdio remains an optional fallback.
The Retail specs describe **expected product behavior**, not a prescribed
MCP workflow. See [Retail Spec 01](../../../examples/scenarios/example/specs/retail-sales-insights-01-app.md)
and [Retail Spec 02](../../../examples/scenarios/example/specs/retail-sales-insights-02-zero-ui.md).
The tool-by-tool demo path is intentionally isolated in the
[presenter's runbook](../../../examples/scenarios/example/demo/execution-guide.md).
Keep platform discovery and execution rules in these agent instructions and
skills, not in product specifications.
