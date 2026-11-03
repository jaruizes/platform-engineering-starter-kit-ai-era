# Software quality and governance

Quality policy is versioned by architecture in `profiles/`. `backend-spring-v2.json` requires JUnit/Surefire, ArchUnit, JaCoCo evidence and SonarQube's server-side quality gate. `frontend-angular-v1.json` requires ESLint, feature boundary checks, Vitest tests, line and branch coverage, production build budgets, and SonarQube's server-side quality gate.

The service pipeline runs `./mvnw verify -DskipITs`, SonarQube analysis with `sonar.qualitygate.wait=true`, then `python3 .platform/quality/gate.py`. The gate sorts report inputs, evaluates the profile, and writes `.platform/quality/results.json` with the source commit SHA and scanner result. The workflow publishes this evidence to the service's `platform-quality-evidence` branch on pass and failure, so MCP and Backstage can report current findings. A failing check stops the workflow before an image is built or the GitOps manifest is changed. SonarQube starts with both `make up` and `make aws-up`; the runner receives an in-cluster URL and a scoped analysis token from a Kubernetes Secret.

To review Sonar manually, run `kubectl -n quality port-forward svc/sonarqube 9000:9000`, open <http://localhost:9000>, and retrieve the administrator password from `sonar-admin-auth` in `platform-system`. `make sonar-up` installs it and provisions credentials; `make sonar-down` removes its data and credentials so it can be cleanly reinitialized.

The Angular Golden Path copies the versioned profile and deterministic gate into each generated service. Its blocking checks run before image publication and GitOps updates. Coverage thresholds start at 70% of lines and 60% of branches; a service with no branches to cover satisfies the branch threshold. Sonar imports `coverage/lcov.info`. E2E/axe journeys, runtime CSP/header checks, OpenAPI client generation and the broader review-only standards are not claimed as automated checks yet.

Use `make demo-quality` to run the template’s ArchUnit check against an invalid dependency, confirm it fails, remove the violation, and confirm it passes.
