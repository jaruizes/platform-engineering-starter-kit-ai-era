# ${{ values.name }}

${{ values.description }}

Angular frontend built and deployed through the platform Golden Path. See
`AGENTS.md` and the `frontend-angular-v1` architecture rules before implementing
features. Requests to the backend use relative `/api/` URLs; the Kubernetes App
resource can route them to `${{ values.backendService }}` in the same environment.

```sh
npm install
npm start
npm run lint
npm test
npm run build
```

The versioned `frontend-angular-v1` quality profile blocks delivery on lint,
feature-boundary violations, unit tests, 70% line coverage, 60% branch
coverage, Angular production budgets, or the SonarQube quality gate. The same
deterministic gate and profile run in CI before an image is published or the
GitOps `App` resource is updated. SonarQube reads the generated LCOV report.

E2E/axe checks, CSP/runtime header verification and OpenAPI client generation
remain architecture requirements for follow-up work; they are not represented
as passing checks in this profile's current pipeline.
