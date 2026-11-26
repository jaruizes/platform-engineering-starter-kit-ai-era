# Agent clients, one platform

`skills/` contains the canonical skills. `instructions/AGENTS.md` is shared repository guidance. `clients/` contains only the transport configuration adapters; no platform code is copied here.

| Client | MCP configuration | Skill discovery | Instructions |
|---|---|---|---|
| Claude Code | `.mcp.json` → `clients/claude-code/mcp.json` | `.claude/skills` → `agents/skills` | `CLAUDE.md` imports shared guidance |
| Codex | `.codex/config.toml` → `clients/codex/config.toml` | `.agents/skills` → `agents/skills` | `AGENTS.md` links shared guidance |
| Gemini CLI | `.gemini/settings.json` → `clients/gemini-cli/settings.json` | `.gemini/skills` → `agents/skills` | `GEMINI.md` imports shared guidance |

Run `make up`, then open the repository with your client. Review the project trust/MCP prompts and verify both `platform` and `portal` servers in the client's MCP listing. All three clients connect to the existing Streamable HTTP services; changing clients does not install a second platform. The checked-in headers are for the local demo only. For AWS, use the public URLs printed by `make aws-up` and the deployment's tokens; keep real credentials outside version control. Codex project config is loaded only for trusted projects.

The platform server handles actions; the portal server supplies context and engineering standards. Identity, policies and approvals remain server responsibilities. A config adapter prepares compatibility; live interoperability still needs each CLI and a running platform.

For new capability skills, create `agents/skills/<name>/SKILL.md` and link `platform/capabilities/<name>/SKILL.md` to it with `../../../agents/skills/<name>/SKILL.md`. The client skill directory links expose it automatically.

Configuration references: [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Codex MCP](https://developers.openai.com/codex/mcp), [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/).
