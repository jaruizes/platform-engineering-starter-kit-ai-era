# Engineering standards

The organization's engineering standards: how a service must be built. In a
real organization this folder is its own repository; the kit keeps it here so
the demo works offline.

Several architectures coexist, as in any organization with some history:

| Architecture | Status | Use it for |
|---|---|---|
| `backend-spring-v2` (hexagonal Spring) | production | New backend services |
| `backend-spring-v1` (layered Spring) | deprecated | Changes to existing layered services |
| `frontend-angular-v1` | production | Internal back-office applications |
| `frontend-react-v1` | production | Customer-facing web applications |

[`architectures.yaml`](architectures.yaml) lists them. Each one has its
`architecture.md`, `architecture-rules.md` and `examples.md` in
`docs/<id>/`; [`docs/common/`](docs/common) applies to all of them. Each
service declares the one it follows with the label
`platform.starterkit.dev/architecture: <id>` in its `catalog-info.yaml`.

Backend v2 and the common documents are taken from the
[My-FinAI-Manager](https://github.com/jaruizes/My-FinAI-Manager/tree/main/reference/engineering)
project; the other architectures are examples written for the demo. Replace
them with your own.

| Who | How they use them |
|---|---|
| People | Read them in the portal (TechDocs, *Engineering standards*) and create services from the **Spring service** template, which already follows them. |
| AI agents | Use the portal MCP server: `platform.get-standards-for-entity` says which architecture and version a service follows and which documents to read; `platform.get-engineering-standard` returns a whole document; `platform.search-engineering-standards` finds a topic, filtered by architecture so versions never mix. The [engineering-standards skill](../../agents/skills/engineering-standards/SKILL.md) tells them to do it in that order. |
| CI | Runs the checks of each architecture (ArchUnit for the backends, ESLint boundary rules and budgets for the frontends), so the rules that can be checked are checked for everyone. |

[`catalog-info.yaml`](catalog-info.yaml) registers the documentation, one
`AiResource` per architecture (with its lifecycle: production or deprecated)
and one per common rule document in the catalog.

## Why not only a RAG

With versions that coexist, similarity search alone mixes rules from
different versions, because their text is alike. So the standards are
structured first: the service says which architecture it follows, and the
agent reads exactly those documents. Search
(`search-engineering-standards`, keyword ranking over sections) covers the
long tail, always filtered by architecture. With many more documents, a
vector index can sit behind the same tool without changing how agents use
it. The portal image builds the
TechDocs site from [`mkdocs.yml`](mkdocs.yml).
