---
name: angular-app
description: Use when a user asks for an Angular frontend, a web UI for a platform service, or an Angular application that calls a Spring backend. Creates it through the platform Golden Path and deploys the Crossplane App resource into an ephemeral Kubernetes environment.
---

# Creating and changing Angular applications

Follow the `frontend-angular-v1` architecture and its rules from the portal's
engineering standards. The Golden Path is `engineering/golden-paths/angular-app`;
it generates a standalone Angular repository and a namespaced Crossplane `App`.

## Create a frontend for a backend

1. Use `create_service` for a requested Spring backend and `create_angular_app`
   for the frontend. Ask for only missing details: repository names, behavior,
   owning team and environment. Pass the backend service name as
   `backend_service` when the frontend calls it.
2. Prefer creating the backend first. The frontend's same-origin `/api/` path
   is proxied by Nginx to that SpringService within the same environment; the
   browser never calls Kubernetes DNS directly.
3. Clone the repository, read `AGENTS.md` and the `frontend-angular-v1`
   architecture rules. Implement the user journeys with feature-first
   boundaries and tests. Use the service's OpenAPI contract for API behavior.

## Verify and deploy

1. Run `npm install`, `npm test` and `npm run build`. Keep the Angular bundle
   budgets in `angular.json` and fix failures rather than weakening checks.
2. Push to the generated repository's `main` only after local checks pass. Its
   pipeline runs tests and the production build, publishes a static Nginx image,
   then updates `deploy/app.yaml`. Argo CD applies `App`; Crossplane reconciles
   its Kubernetes Deployment and internal Service.
3. Poll `get_service_status(name, environment, resource_kind="App")` until
   ready. Run the specification's browser acceptance checks against the
   deployed frontend and report its repository, tested commit, environment and
   results.

Do not write Kubernetes resources directly or bypass the Golden Path. Keep
frontend API calls on relative `/api/` routes so the platform proxy and browser
same-origin policy continue to apply.
