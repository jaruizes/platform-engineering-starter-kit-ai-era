# Software quality and governance

Quality policy is versioned by architecture in `profiles/`. `backend-spring-v2.json` requires JUnit/Surefire, ArchUnit, JaCoCo evidence and SonarQube's server-side quality gate.

The service pipeline runs `./mvnw verify -DskipITs`, SonarQube analysis with `sonar.qualitygate.wait=true`, then `python3 .platform/quality/gate.py`. The gate sorts report inputs, evaluates the profile, and writes `.platform/quality/results.json` with the source commit SHA and scanner result. The workflow publishes this evidence to the service's `platform-quality-evidence` branch on pass and failure, so MCP and Backstage can report current findings. A failing check stops the workflow before an image is built or the GitOps manifest is changed. SonarQube starts with both `make up` and `make aws-up`; the runner receives an in-cluster URL and a scoped analysis token from a Kubernetes Secret.

To review Sonar manually, run `kubectl -n quality port-forward svc/sonarqube 9000:9000`, open <http://localhost:9000>, and retrieve the administrator password from `sonar-admin-auth` in `platform-system`. `make sonar-up` reapplies its manifests; `make sonar-down` removes its data and should only be used when the platform is stopped.

Use `make demo-quality` to run the template’s ArchUnit check against an invalid dependency, confirm it fails, remove the violation, and confirm it passes.
