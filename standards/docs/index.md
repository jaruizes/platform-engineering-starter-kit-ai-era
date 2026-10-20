# Engineering standards

How services are built in this organization. These documents are the single
source of truth for people and for AI agents.

| Document | What it answers |
|---|---|
| [Architecture](architecture.md) | How the system is structured and why: hexagonal architecture, the Spring package model, interaction, persistence, AI providers. |
| [Architecture rules](architecture-rules.md) | What must be true for code to be compliant (AAC-001 to AAC-022). |
| [Technology policy](technology-policy.md) | Which technologies are allowed, and when. |
| [Development rules](development-rules.md) | Implementation discipline (DR-001 to DR-023), for human and AI-written code alike. |
| [Testing](testing.md) | How correctness is proven at each level. |

## How the platform uses them

- **People** read them here and start new services from the **Spring service**
  template, whose skeleton already follows them.
- **AI agents** read them through the portal MCP server
  (`platform.list-engineering-standards`, `platform.get-engineering-standard`) and create
  services through the same template (`create_service` in the platform MCP
  server). Every generated repository has an `AGENTS.md` with the essentials.
- **Nobody has to remember them**: the rules that can be checked are checked.
  Each generated service runs ArchUnit tests for the package structure and
  dependency direction in `./mvnw verify`, locally and in CI, for human and
  AI-written code alike.
