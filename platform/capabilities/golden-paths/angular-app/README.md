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


## CSP: Angular/Material styles in deployed apps

The Crossplane Angular composition configures a strict CSP. Angular injects
component `<style>` tags at runtime; **`default-src 'self'` alone blocks them**.
The runtime now issues `style-src 'self' 'nonce-$request_id'`, substitutes
`__CSP_NONCE__` in the HTML `<app-root ngCspNonce="...">`, and prevents
HTML caching to avoid serving an old nonce. Nginx's `$request_id` is a fresh
16-byte random identifier encoded as hexadecimal. Angular reads the nonce
from its root element, including styles inserted by Angular Material.
Production builds disable `inlineCritical` so CLI-generated critical styles
do not bypass the nonce arrangement.

**Validation:** from an active port-forward, inspect the HTTP CSP header and
HTML `ngCspNonce` value; they must match and change between HTML requests.
Check the browser console for CSP violations and inspect injected `<style>`
elements. Avoid adding `'unsafe-inline'` or disabling CSP to hide the failure.

**Existing generated apps:** the CSP header comes from the platform Crossplane
Composition. Redeploy/update the platform composition so the existing App's
Nginx ConfigMap reconciles. Older generated Angular repositories also need
the updated `src/index.html` and production `angular.json` configuration,
followed by a new image and deployment. The runtime alone does not inject
`ngCspNonce` into an app built from an old template.
