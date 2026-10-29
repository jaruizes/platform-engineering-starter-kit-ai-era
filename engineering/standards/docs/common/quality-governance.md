# Quality governance

This policy defines the evidence a change must produce before the platform can update GitOps manifests. Its purpose is to make the organization’s engineering criteria executable for both people and agents, and to return precise findings so an agent can correct its implementation.

## Architecture-specific profiles

Each architecture and version has a versioned profile under `engineering/quality/profiles/`. A service declares its architecture in the catalog; the Golden Path copies the matching profile into `.platform/quality/profile.json` in the service repository. The first profile is `backend-spring-v2`, version 1.

The profile defines blocking checks. For Spring v2 they are:

- **JUnit/Surefire:** tests ran and there are no failures or errors.
- **ArchUnit:** the architecture suite ran and did not fail.
- **JaCoCo:** a line coverage report was produced. Coverage is reported with the result; the initial minimum is 0% because the generated skeleton contains no business behavior. Numeric thresholds belong in the profile and should reflect an agreed organizational baseline.

SonarQube is an optional advisory analysis. Its absence or unavailability does not bypass or replace the deterministic profile gate.

## Delivery and evidence

The Gitea Actions pipeline evaluates the deterministic gate after Maven verification and before building/deploying. A failed check prevents any image reference from being written to `deploy/app.yaml`. The pipeline writes structured JSON with the source commit, architecture, profile version, each check, and findings. It publishes this file to the service branch `platform-quality-evidence` on pass and failure.

The platform MCP tool `get_quality_status` is read-only and returns the latest evidence and failed checks. The Backstage service page shows the same result. An agent should use the check findings and JUnit/ArchUnit output to fix the code, rerun the gate, and report the tested commit. Editing result files, relaxing a profile, suppressing tests, or bypassing the gate is not a valid correction.
