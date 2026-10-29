# Software quality and governance

Quality policy is versioned by architecture in `profiles/`. `backend-spring-v2.json` starts with JUnit/Surefire, ArchUnit and a JaCoCo report as mandatory evidence. Coverage is reported as a diagnostic signal; the initial floor is 0% because this template contains no business behavior. Raise the profile floor with the organization’s baseline.

The service pipeline runs `./mvnw verify -DskipITs`, then `python3 .platform/quality/gate.py`. The gate sorts report inputs, evaluates the profile, and writes `.platform/quality/results.json` with the source commit SHA. The workflow publishes this evidence to the service's `platform-quality-evidence` branch on both pass and failure, so MCP and Backstage can report current findings. A failing gate stops the workflow before the GitOps image manifest is changed. Passing evidence records the tested source SHA and profile version.

SonarQube is optional and advisory. Configure `SONAR_HOST_URL` (for the in-cluster demo, `http://sonarqube.quality.svc:9000`) and `SONAR_TOKEN` in Gitea repository variables/secrets to run the pinned Maven Sonar scanner. `make sonar-up` installs the demo server in the current cluster (local or AWS); `make sonar-down` removes it. The deterministic quality gate does not depend on Sonar availability.

Use `make demo-quality` to run the template’s ArchUnit check against an invalid dependency, confirm it fails, remove the violation, and confirm it passes.
