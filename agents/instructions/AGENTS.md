# Working on the platform

Read `README.md` for the layout and commands. All paths below are repository-relative.

- Keep platform implementation in `platform/`, user and agent interfaces in `interfaces/`, and engineering contracts in `engineering/`.
- Read the applicable skill in `agents/skills/` before requesting infrastructure or building a capability. These are the canonical skills for every client.
- Use the same platform and portal MCP servers from every client. Request infrastructure through the Golden Paths and capability APIs; keep identity, guardrails and approvals on the server.
- Capability definitions live in `platform/capabilities/<name>/capability.yaml`. Preserve their interface and acceptance criteria during implementation.
- Store new skills in `agents/skills/<name>/SKILL.md`. Capabilities retain a relative `SKILL.md` link to that source. Client discovery directories link to `agents/skills`; do not copy skills per client.
- Preserve `make up`, `make aws-up`, `make test` and `make capability NAME=<name>`.
- Run `python3 bootstrap/check-repository.py`, `make test` and the relevant capability checks. Report unavailable dependencies or cluster checks honestly.
- Do not add SonarQube. Do not merge or push changes to `main` without explicit authorization.
