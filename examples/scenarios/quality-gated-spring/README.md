# Quality gated Spring service on AWS

This scenario exercises the platform as a harness: an agent turns a product
spec into a Spring service through the platform template, CI applies the same
quality controls to human and agent changes, and GitOps deploys only a passing
commit to an ephemeral environment.

The product request is [`discount-service.md`](../example/specs/discount-service.md).
It defines the service, its API, business rules, sample customers and
acceptance criteria. The repo template and platform policy supply the
architecture and technical constraints.

## Prepare the harness

Run `make aws-up` (SonarQube is installed and started as part of this command),
then connect the coding agent to the printed `platform` and `portal` MCP
servers. The cluster needs to be reachable through the configured AWS
credentials and `kubectl` context. Trust the generated CA for browser and Git
access as described by the command output.

To inspect Sonar manually, start a local tunnel and open its UI:

```bash
kubectl -n quality port-forward svc/sonarqube 9000:9000
```

Open <http://localhost:9000>. The username is `admin`; retrieve the generated
password with:

```bash
kubectl -n platform-system get secret sonar-admin-auth -o jsonpath='{.data.password}' | base64 -d
```

## Ask the agent

Give it this task, attaching or pointing it at the spec:

> Implement `examples/scenarios/example/specs/discount-service.md` as a new
> Spring service. Use the platform Golden Path and the `spring-service` skill;
> do not scaffold by hand. Request a small 8-hour ephemeral environment for
> team `checkout`, create `discount-service` from the template with that
> environment, implement the acceptance criteria and tests, run the
> architecture-specific quality checks, and push the passing change to the
> service repository's `main`. Then follow the delivery through the platform
> MCP server until it is ready. Do not deploy by hand or weaken a quality rule.

Expected platform flow:

1. The agent reads the spec and asks `request_environment` for a small,
   time-limited environment, then checks readiness with `get_environment`.
2. It calls `create_service` with `name=discount-service`, `team=checkout`,
   `module=discounts` and the environment name. This runs the same Backstage
   template as a human and gives the agent a repository with architecture
   rules, CI and GitOps manifests.
3. It clones the repository, implements the API and business rules in
   `discounts/domain`, `discounts/business` and
   `discounts/infrastructure/api/rest`, and adds tests. It runs the generated
   checks and pushes the implementation.
4. Gitea Actions runs JUnit, ArchUnit, JaCoCo and a blocking SonarQube analysis
   with the server quality gate. Any failure blocks image publication and
   prevents the GitOps manifest update. Passing evidence records the source
   commit and profile version.
5. The image is built and pushed; Argo CD deploys it with its PostgreSQL
   capability into the ephemeral environment. The agent polls
   `get_service_status` until ready.
6. Run the black-box acceptance checks from this folder:

   ```bash
   ./run-e2e.sh discount-service <environment-name>
   ```

The end-to-end script port-forwards the service and checks the expected
discounts for customers C001 through C005. It uses only the service API; it
does not inspect implementation details.

## Human review

Open the service's project in SonarQube to review its quality gate and findings.
The platform MCP tool `get_quality_status` and the Backstage service quality
card show the commit-linked gate result and deterministic findings. If quality
fails, the agent should read the findings, make the smallest correction, rerun
the same checks and push a new commit. A human remains responsible for
acceptance decisions that cannot be expressed as automated tests and for
approving any required ADR.
