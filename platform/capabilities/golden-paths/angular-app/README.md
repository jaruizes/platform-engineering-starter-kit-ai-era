# Angular application Golden Path

This Golden Path creates a standalone Angular frontend repository, ready to build
as a container and deploy in an ephemeral Kubernetes environment.

- `template.yaml` is the Backstage scaffolder template.
- `skeleton/` is the generated application, container build and GitOps manifest.
- `runtime/definition.yaml` and `runtime/composition.yaml` define the namespaced
  Crossplane `App` resource. It reconciles a Deployment and ClusterIP Service.

Set `backendService` to a SpringService name in the same environment to route
requests made to `/api/` through the frontend's Nginx server to that service.
Use relative `/api/` URLs in Angular so the browser does not need Kubernetes
DNS or cross-origin access.


## Build and verification

Angular 20's unit-test builder generates code coverage via `codeCoverage` and
`codeCoverageReporters` in `angular.json`; `npm test` normalizes LCOV
source paths to repository-relative `src/...` for SonarQube. The
`sonar-project.properties` file excludes `*.spec.ts` from production sources
and categorizes them as tests. Run `npm run test:lcov` to verify the
normalizer independently.

The delivery pipeline builds a **multi-architecture** Nginx image
(`linux/amd64`, `linux/arm64`) with `crane append --new_layer --new_tag`
and `crane index append`, then deploys only the final index tag. The runner
must be allowed to push all tags to ECR or the local registry.
