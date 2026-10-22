# ${{ values.name }}

${{ values.description }}

Owner: ${{ values.owner }}. Created from the platform's **Spring service**
template, following the
[engineering standards](http://localhost:7007/docs/default/component/engineering-standards) for backend v2
(hexagonal Spring).

## Run the checks

```bash
./mvnw verify   # unit tests, architecture rules (ArchUnit) and integration tests
```

Integration tests start PostgreSQL with Testcontainers, so Docker must be
running.

## Structure

`${{ values.rootPackage }}.${{ values.module }}` is the first functional module,
with its `domain`, `business` and `infrastructure` packages. The architecture
rules that keep this structure are in
`src/test/java/**/architecture/ArchitectureTest.java`.

AI agents: read [AGENTS.md](AGENTS.md).
