# Agent capabilities

What the platform team offers the coding agents of every team, as
[Claude Code plugins](https://code.claude.com/docs/en/plugins). The Golden
Paths give people a paved road instead of each team building its own
infrastructure; these plugins do the same for agents, instead of each team
writing its own prompts that nobody shares.

| Plugin | What it brings | Who needs it |
|---|---|---|
| [`platform`](platform/) | The connection to the platform (`platform` and `portal` MCP servers), the skills to use them ([Golden Paths](platform/skills/platform-golden-paths/SKILL.md), [Spring services](platform/skills/spring-service/SKILL.md), [engineering standards](platform/skills/engineering-standards/SKILL.md) and one per [platform capability](../capabilities/)), and a [hook](platform/hooks/use-golden-paths.sh) that stops the agent from changing infrastructure from its shell | Every team |
| [`dev-team`](dev-team/) | The roles of a development team as subagents, two skills to work from specs, and the commands that start them | Teams that build services from specs |

## The development team

| Kind | Name | What it does |
|---|---|---|
| Subagent | [`backend-developer`](dev-team/agents/backend-developer.md) | Implements a backend change following the service's architecture, until `./mvnw verify` passes |
| Subagent | [`frontend-developer`](dev-team/agents/frontend-developer.md) | Implements a web change following Angular v1 or React v1 |
| Subagent | [`qa-engineer`](dev-team/agents/qa-engineer.md) | Turns acceptance criteria into tests, boundaries included, and finds criteria that contradict the rules |
| Subagent | [`architect`](dev-team/agents/architect.md) | Reviews a change against the architecture rules and technology policy, with rule ids; drafts ADRs; never edits code |
| Skill | [`review-spec`](dev-team/skills/review-spec/SKILL.md) | Checks a spec is complete, consistent and testable, with a [spec template](dev-team/skills/review-spec/spec-template.md) |
| Skill | [`implement-spec`](dev-team/skills/implement-spec/SKILL.md) | From spec to a deployed service the user can call: review, environment, `create_service`, tests, implementation, review, push, `get_service_status` |
| Command | `/dev-team:review-spec <spec>` | Reviews a spec and changes nothing |
| Command | `/dev-team:implement-spec <spec>` | Implements a spec end to end |
| Command | `/dev-team:review-architecture` | Asks the architect to review the current changes before a push |

Roles are subagents because each one has its own way of working; skills are
what any role knows how to do. The commands are the reusable prompts: the
same request, worded the same way, in every team.

## How teams get them

- **New services**: repositories created from the Spring service template
  have a `.claude/settings.json` that offers both plugins from the platform's
  Git server the first time someone opens them in Claude Code.
- **Any other repository**: in Claude Code,
  `/plugin marketplace add http://localhost:3000/platform/platform-starter-kit.git`
  (or `jaruizes/platform-engineering-starter-kit-ai-era` from GitHub), then
  `/plugin install platform@platform-starter-kit` and
  `/plugin install dev-team@platform-starter-kit`.
- **The portal** lists the marketplace, both plugins and their skills under
  *AI resources* (`portal/catalog/ai.yaml`).

The `platform` plugin reads `PLATFORM_MCP_URL`, `PORTAL_MCP_URL` and
`PORTAL_MCP_TOKEN` when the platform is not on localhost.

## Who owns what

The platform team owns these plugins: they encode *how* things are built
here, and they change with the standards and the Golden Paths. A team owns
*what* it builds and how it works: it adds its own subagents, skills and
commands in its repository (`.claude/agents`, `.claude/skills`,
`.claude/commands`) and they sit next to the platform's. A team role that
other teams want too comes here as a pull request.

## Changing them

- Skills come from the same sources as the rest of the platform: the
  `platform` skills are linked from `.claude/skills/` (so the platform
  repository uses them too), and each capability's skill is linked from
  `capabilities/<name>`. Do not copy them.
- Bump `version` in the plugin's `.claude-plugin/plugin.json` and in
  [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)
  when a plugin changes, so teams get the update.
- `.github/workflows/agent-capabilities.yml` validates the marketplace and
  the plugins, installs them as a team would, and runs
  [the hook tests](tests/use-golden-paths.sh).
