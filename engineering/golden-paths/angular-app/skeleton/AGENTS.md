# Working in ${{ values.name }}

Before changing this application, read the `frontend-angular-v1` architecture,
its architecture rules, and the common development and testing standards from
the platform. Keep screens and business behavior in feature folders, use
relative `/api/` URLs for backend contracts, and add tests for user-visible
behavior. Run `npm run lint`, `npm test`, and `npm run build` before delivery.

Install dependencies with `npm install` (the first install creates the lockfile).
The platform creates `App` from `deploy/app.yaml`. The delivery pipeline writes
the built image there after checks pass. Optional `backendService` configures
the in-cluster `/api/` reverse proxy.
