# Frontend architecture: Angular v1

## Purpose

Angular v1 is the standard architecture for internal back-office and operations applications: authenticated employees working with data-heavy forms and tables. It uses standalone components, signals, OnPush change detection and HTTP clients generated from the Business API contract.

This document explains how such an application is structured and why. The verifiable acceptance criteria are in `architecture-rules.md` (FA-001 to FA-016). Implementation discipline shared by all architectures (naming, error handling, secrets, dependencies, generated code) is in `common/development-rules.md` and is not repeated here. Testing principles are in `common/testing.md`.

---

# 1. When to use it

Use Angular v1 when:

- the users are employees, authenticated through the corporate identity provider;
- the work is mostly forms, tables, filters, bulk actions and detail pages;
- the application lives behind the gateway and does not need SEO or server-side rendering;
- the team values a strongly opinionated framework with batteries included (router, forms, HTTP, i18n, testing).

Use the **React architecture** (`frontend-react-v1`) instead for customer-facing web: public pages, marketing-sensitive performance, SEO, or experiences shared with mobile web teams.

Do not create a frontend for a single screen that an existing back-office already covers. Add a feature to that application instead.

---

# 2. Position in the platform

The frontend talks only to the backend, through the **Business API** (OpenAPI contracts) or, when justified, through an application-specific **BFF**. It never talks to databases, Kafka topics, internal services, market-data providers or LLM providers.

```text
Browser (Angular app) ──HTTPS──▶ Gateway ──▶ Business API / BFF ──▶ internal services
```

Business rules live in the backend. The frontend validates input for user experience, but the backend is the authority.

---

# 3. Folder structure

The application is organized feature-first. Each feature is a vertical slice that can be understood, tested and lazy-loaded on its own.

```text
src/
├── app/
│   ├── app.config.ts          # providers: router, HTTP, interceptors, i18n
│   ├── app.routes.ts          # top-level routes, one lazy entry per feature
│   ├── core/                  # singletons: auth, interceptors, error handling, telemetry, layout shell
│   ├── shared/                # reusable UI (no business logic), pipes, directives, utilities
│   ├── api/                   # generated OpenAPI clients (never edited by hand)
│   └── features/
│       └── <feature>/
│           ├── <feature>.routes.ts
│           ├── pages/         # routed components, wire store to components
│           ├── components/    # presentational components (inputs/outputs only)
│           ├── data-access/   # services wrapping the generated client, signal stores
│           └── models/        # view models and mappers
├── environments/              # build-time defaults only; runtime config is loaded
└── styles/                    # design tokens, global theme
```

Dependency direction:

```text
features/<x>  → shared, core, api (via data-access only)
shared        → nothing in features
core          → shared, api
features/<x>  ✗ features/<y>
```

A feature never imports another feature. If two features need the same thing, it moves to `shared` (UI) or becomes a backend concern (data). These rules are enforced by ESLint boundary rules, not by review.

---

# 4. Components and change detection

- All components, directives and pipes are **standalone**. NgModules are not used.
- All components use `ChangeDetectionStrategy.OnPush`.
- Use the signal APIs: `input()`, `output()`, `model()`, `viewChild()`, `computed()`.
- Use the built-in control flow (`@if`, `@for` with `track`, `@switch`) and `@defer` for heavy, below-the-fold blocks.
- Inject with `inject()`, not constructor parameters.

There are two kinds of component:

- **Pages** (`pages/`) are routed. They inject the feature store, read its signals and pass data down. They contain no layout-heavy markup.
- **Presentational components** (`components/`, `shared/`) receive data through inputs and emit events through outputs. They do not inject stores or data-access services, which keeps them trivial to test and reuse.

Subscriptions in templates use signals or `toSignal()`. Manual `subscribe()` in components is avoided; when unavoidable, it uses `takeUntilDestroyed()`.

---

# 5. State

State is held in signals, at the smallest scope that works:

| Scope | Where | Tool |
|---|---|---|
| Component-local UI state | the component | `signal()`, `computed()` |
| Feature state | `data-access/<feature>.store.ts` | signal store service provided on the feature route |
| Complex feature state (many entities, undo, optimistic updates) | `data-access/` | NgRx SignalStore |
| Session state (user, permissions, locale) | `core/` | root-provided signal store |

A feature store is provided on the feature's route, so it is created when the user enters the feature and destroyed when they leave. Stores expose read-only signals and intention-revealing methods (`load()`, `approve(id)`), never writable signals.

Global NgRx Store (actions, reducers, effects) is not used for new applications. RxJS remains the tool for streams and HTTP; convert to signals at the store boundary.

Server data is not duplicated across stores. The URL holds navigational state (filters, page, sort, selected id) so that views are shareable and survive reload.

---

# 6. Routing

- `app.routes.ts` declares one lazy route per feature with `loadChildren: () => import(...)`.
- Each feature exports its own `<feature>.routes.ts` with route-level `providers` for its store.
- Guards and resolvers are functional (`CanActivateFn`, `ResolveFn`).
- Access control uses a functional guard that checks roles from the session store. The backend still enforces authorization on every call; the guard only improves UX.
- Route parameters are bound to inputs with `withComponentInputBinding()`.

---

# 7. Talking to the backend

HTTP clients are **generated** from the backend's OpenAPI contract with `openapi-generator` (`typescript-angular`) into `src/app/api/`. The generated code is never edited by hand and is regenerated in CI when the contract version changes.

Generated clients are not used directly by pages or components. Each feature has data-access services that:

- wrap the generated client;
- map transport DTOs to feature view models (`models/`);
- translate errors into feature-level outcomes;
- are the only place in the feature that performs HTTP.

Interceptors in `core/` handle cross-cutting concerns:

- **auth**: attaches the OIDC access token to requests to the API origin only;
- **errors**: maps `ProblemDetails` responses to user messages, redirects on 401, shows a generic message on 5xx and reports the error to telemetry;
- **correlation**: propagates the W3C `traceparent` header.

Runtime configuration (API base URL, OIDC issuer, client id, telemetry endpoint) is loaded from `/config.json` at startup, so the same build artifact runs in every environment.

---

# 8. Forms and validation

- Use **typed reactive forms** (`FormGroup<...>`, `NonNullableFormBuilder`). Untyped forms and template-driven forms are not used for business data.
- Validators that mirror backend constraints (required, length, format) live next to the form model. Cross-field validators are pure functions.
- Server-side validation errors (`ProblemDetails` with field errors) are mapped back onto form controls.
- Form state (dirty, pending, submitting) is exposed as signals to the template. A `CanDeactivateFn` warns about unsaved changes on long forms.
- Money, quantities and identifiers follow the precision rules of `common/development-rules.md` (DR-005): no floating-point arithmetic on monetary values in the browser.

---

# 9. UI and design system

- **Angular Material** (with the CDK) is the component library. Its theme is generated from the company **design tokens** (`styles/tokens`), so colors, spacing and typography come from one source.
- Tables use `mat-table` with server-side paging, sorting and filtering. Large lists use CDK virtual scrolling.
- Shared building blocks (page header, filter bar, empty state, confirm dialog) live in `shared/ui` and are reused, not re-styled per feature.
- No hard-coded colors or pixel spacing in component styles: use tokens.
- Another UI library requires an ADR.

---

# 10. Security

- Authentication uses **OIDC Authorization Code with PKCE** against the corporate identity provider, through a maintained library (for example `angular-auth-oidc-client`). Tokens are kept in memory or session storage, never in `localStorage`. When a BFF is used, prefer its session cookie and keep tokens out of the browser.
- The access token is sent only to the configured API origin.
- No secrets in the bundle. Anything shipped to the browser is public.
- Do not bypass Angular sanitization (`bypassSecurityTrust*`) without an ADR. Do not use `innerHTML` with untrusted content.
- A strict Content Security Policy is set by the serving container; Angular is built to be compatible with it (no inline scripts, `autoCsp` or nonces).
- Dependencies are scanned in CI like any other artifact.

---

# 11. Internationalization and accessibility

- All user-visible text is marked with `@angular/localize` (`i18n` attributes, `$localize`). Translations are extracted to XLIFF and one bundle is built per locale.
- Dates, numbers and currencies use Angular locale-aware pipes, never string formatting.
- Accessibility target is **WCAG 2.2 AA**: keyboard reachability of every action, visible focus, labelled form controls, meaningful error messages tied to fields, sufficient contrast (guaranteed by tokens), and correct table semantics.
- Automated checks (axe) run in component tests and in E2E tests. Automation does not replace a manual keyboard pass on new pages.

---

# 12. Performance budgets

Back-office apps are used all day; responsiveness matters more than first-visit speed, but budgets still apply and are enforced by the build (`angular.json` budgets) in CI:

| Budget | Limit |
|---|---|
| Initial bundle (per locale) | 500 kB warning, 800 kB error (compressed transfer ~200 kB) |
| Any lazy feature chunk | 300 kB warning, 500 kB error |
| Component style | 6 kB warning, 10 kB error |

Additional guidance: lazy-load every feature, use `@defer` for heavy widgets (charts, editors), page and filter on the server, and avoid importing whole utility libraries.

---

# 13. Testing

Testing follows `common/testing.md`. Frontend specifics:

- **Unit and component tests** with Jest or Vitest (one per repository) and **Angular Testing Library**. Tests interact with components the way users do (roles, labels), not through internals.
- Stores and data-access services are tested with the generated client mocked or with `HttpTestingController`.
- **Contract alignment** comes from generation: if the contract changes incompatibly, the build fails.
- **Playwright** E2E covers a small number of critical journeys (log in, search, edit, submit) against a deployed environment or a mocked API. E2E is not used to test every branch.
- Boundary rules and budgets are tests too: they run in CI.

---

# 14. Observability

- The **OpenTelemetry Web SDK** is initialized in `core/` with document load, fetch/XHR and user-interaction instrumentation. Traces are exported to the platform collector through the gateway, and `traceparent` links browser spans to backend traces.
- A global `ErrorHandler` reports unhandled errors with route, release version and trace id. No personal data, tokens or form contents are sent.
- Core Web Vitals (LCP, INP, CLS) are collected as metrics.
- Console logging is removed in production builds.

---

# 15. Build and deployment

- `ng build` (application builder, esbuild) produces static assets per locale.
- The artifact is a **static container** (for example unprivileged nginx) that serves the assets, `config.json` and security headers (CSP, HSTS, `X-Content-Type-Options`). Hashed assets are cached long-term; `index.html` and `config.json` are not cached.
- The container runs **behind the gateway**, which handles TLS and routing. The frontend is never exposed directly.
- The same image is promoted across environments; only `config.json` changes.
- The CI pipeline runs lint (including boundaries), unit and component tests, build with budgets, OpenAPI client generation check, and E2E on the critical journeys.
