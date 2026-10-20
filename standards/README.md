# Engineering standards

The organization's engineering standards: how a service must be built. In a
real organization this folder is its own repository; the kit keeps it here so
the demo works offline.

The documents in [`docs/`](docs/) are an example taken as they are from the
[My-FinAI-Manager](https://github.com/jaruizes/My-FinAI-Manager/tree/main/reference/engineering)
project. Replace them with your own.

| Who | How they use them |
|---|---|
| People | Read them in the portal (TechDocs, *Engineering standards*) and create services from the **Spring service** template, which already follows them. |
| AI agents | Read them through the portal MCP server (`platform.list-engineering-standards`, `platform.get-engineering-standard`), create services with `create_service` in the platform MCP server, and follow the `AGENTS.md` of each generated repository. |
| CI | Runs the ArchUnit tests generated with each service (`./mvnw verify`), so the rules that can be checked are checked for everyone. |

[`catalog-info.yaml`](catalog-info.yaml) registers the documentation and one
`AiResource` per rule document in the catalog. The portal image builds the
TechDocs site from [`mkdocs.yml`](mkdocs.yml).
