# Engineering standards

How software is built in this organization. These documents are the single
source of truth for people and for AI agents.

## Several architectures, side by side

Services are not all built the same way, and that is fine as long as each one
follows a known architecture, in a known version. Each service says which one
in its `catalog-info.yaml`:

```yaml
metadata:
  labels:
    platform.starterkit.dev/architecture: backend-spring-v2
```

| Architecture | Status | Use it for |
|---|---|---|
| [Backend v2 (hexagonal Spring)](backend-spring-v2/architecture.md) | production | New backend services and new modules in v2 services. Template: **Spring service**. |
| [Backend v1 (layered Spring)](backend-spring-v1/architecture.md) | deprecated | Existing layered services only: bug fixes and small features. Migrate to v2 module by module. |
| [Frontend Angular v1](frontend-angular-v1/architecture.md) | production | Internal back-office and operations applications. |
| [Frontend React v1](frontend-react-v1/architecture.md) | production | Customer-facing web applications. |

Each architecture has three documents: **architecture** (how it is structured
and why), **architecture rules** (what must be true to be compliant, with
ids such as `AAC-001`, `BL-001`, `FA-001` or `FR-001`) and **examples**
(compliant and non-compliant code). The list of architectures is in
`architectures.yaml`.

## For every architecture

| Document | What it answers |
|---|---|
| [Technology policy](common/technology-policy.md) | Which technologies are allowed, and when. |
| [Development rules](common/development-rules.md) | Implementation discipline (DR-001 to DR-023), for human and AI-written code alike. |
| [Testing](common/testing.md) | How correctness is proven at each level. |

## How the platform uses them

- **People** read them here and start new backend services from the **Spring
  service** template, whose skeleton already follows backend v2.
- **AI agents** use the portal MCP server. To change a service, they call
  `platform.get-standards-for-entity`, which returns the architecture and
  version that service follows and the documents to read, in order. They
  read whole documents with `platform.get-engineering-standard` and find a
  specific topic with `platform.search-engineering-standards`, filtered by
  the architecture so rules from another version never mix in.
- **Nobody has to remember them**: the rules that can be checked are checked
  in CI (ArchUnit for the backends, ESLint boundary rules and budgets for the
  frontends), for human and AI-written code alike.
