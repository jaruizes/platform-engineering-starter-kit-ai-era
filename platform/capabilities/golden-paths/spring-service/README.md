# Spring service Golden Path

This is the end-to-end path for creating and running a Spring service:

- `template.yaml` is the Backstage software template used by people and by the platform MCP `create_service` flow.
- `skeleton/` is the repository created from that template, including the Spring structure, tests, CI pipeline, and GitOps declarations.
- `runtime/definition.yaml` and `runtime/composition.yaml` define the Crossplane `SpringService` resource. Argo CD applies the `SpringService` declaration from `deploy/spring-service.yaml`; Crossplane reconciles it into Kubernetes workload resources.

The portal image includes this directory as a build context so the template and its relative `skeleton/` remain available to Backstage at runtime.

## Existing service repositories

This rename does not rewrite repositories that were generated from the former template. Those repositories still use the former `App` resource and `deploy/app.yaml` until migrated. Update the manifest to `kind: SpringService` in `deploy/spring-service.yaml` and adjust the delivery workflow to write the image there before relying on the new runtime resource.


## CI coverage and Testcontainers

The Gitea runner currently executes `./mvnw verify -DskipITs` because it
cannot run Docker-based Testcontainers. This is a deliberate deployment
constraint, **not an indication that integration tests passed**. JaCoCo and
SonarQube therefore see only coverage from the unit suite, and persistence
adapters exercised solely by integration tests may fail Sonar coverage.

Golden Path users must add unit tests for persistence adapters and
business use cases, run `./mvnw verify` locally with Docker, and keep the
existing Sonar gate blocking. A future upgrade can run integration tests in
CI using an isolated, supported Docker/Testcontainers executor.
