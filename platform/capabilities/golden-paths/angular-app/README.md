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
