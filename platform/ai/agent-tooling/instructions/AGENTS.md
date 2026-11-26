# Working on the platform

Read `README.md` for the layout and commands. All paths below are repository-relative.

- Follow logical architecture: `platform/access`, `platform/capabilities`, `platform/ai`, `platform/cognitive`, `platform/governance`, `platform/integrations`, and `deploy`.
- Read the applicable skill in `platform/ai/agent-tooling/skills/` before requesting infrastructure or building a capability. These are the canonical skills for every client.
- Use the same platform and portal MCP servers from every client. Request infrastructure through the Golden Paths and capability APIs; keep identity, guardrails and approvals on the server.
- Capability definitions live in `platform/capabilities/infrastructure/<name>/capability.yaml`. Preserve their interface and acceptance criteria during implementation.
- Store new skills in `platform/ai/agent-tooling/skills/<name>/SKILL.md`. Capabilities retain a relative `SKILL.md` link to that source. Client discovery directories link to `platform/ai/agent-tooling/skills`; do not copy skills per client.
- Preserve `make up`, `make aws-up`, `make test` and `make capability NAME=<name>`.
- Run `python3 deploy/check-repository.py`, `make test` and the relevant capability checks. Report unavailable dependencies or cluster checks honestly.
