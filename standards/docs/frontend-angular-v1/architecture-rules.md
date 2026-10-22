# Architecture rules: frontend Angular v1

## Purpose

These are the verifiable acceptance criteria for an Angular v1 back-office application: what must be true for a frontend implementation to be architecture-compliant.

This document does not restate the architecture. The intent, structure and rationale are in `architecture.md` of this architecture. Shared implementation discipline is in `common/development-rules.md` and applies in addition to these rules.

---

# Acceptance Model

Rules are classified as:

- **MANDATORY** — failure means architecture validation is `KO`, unless an approved ADR explicitly authorizes the exception.
- **CONDITIONAL** — mandatory when the described situation exists.
- **RECOMMENDED** — deviation should be justified when material.

Each rule states how it is verified. Rules marked **[ESLint]** are enforced by `@angular-eslint` and boundary rules (`eslint-plugin-boundaries` or Nx module boundaries) in `npm run lint`. Rules marked **[CI budget]** are enforced by Angular build budgets. Both run locally and in CI, and a failure blocks the merge.

---

# 1. Structure and Boundaries

## FA-001 — Feature-First Structure

**MANDATORY**

The application follows the structure in `architecture.md`:

```text
src/app/{core,shared,api,features/<feature>/{pages,components,data-access,models}}
```

Every routed screen belongs to exactly one feature.

Verified by: **[ESLint]** boundary element patterns (files outside a known element fail).

---

## FA-002 — Features Do Not Import Other Features

**MANDATORY**

Code in `features/<x>` must not import from `features/<y>`.

`shared` must not import from `features`. `core` must not import from `features`, except `app.routes.ts` for lazy route entries.

Verified by: **[ESLint]** boundary rules.

---

## FA-003 — HTTP Only in Data-Access

**MANDATORY**

Only `features/*/data-access` and `core` (interceptors, configuration, auth) may inject `HttpClient` or generated API services from `api/`.

Pages, components, `shared` and `models` must not.

Verified by: **[ESLint]** boundary rules plus `no-restricted-imports` on `@angular/common/http` and `api/`.

---

## FA-004 — Backend Access Only Through the Business API or BFF

**MANDATORY**

The browser calls only the Business API or the application's BFF, through the gateway.

Direct access to databases, message brokers, internal services, third-party data providers or LLM providers is forbidden.

Verified by: review of runtime `config.json` origins and the CSP `connect-src` directive, which lists only the gateway and the telemetry endpoint.

---

## FA-005 — Generated API Clients

**MANDATORY**

HTTP clients are generated from the backend OpenAPI contract with `openapi-generator` into `src/app/api/`. Generated code is not edited by hand. Hand-written HTTP calls to Business API endpoints are not allowed.

Verified by: CI regenerates clients from the pinned contract version and fails on diff.

---

# 2. Components and State

## FA-006 — Standalone and OnPush

**MANDATORY**

All components, directives and pipes are standalone. No `@NgModule` is declared. All components use `ChangeDetectionStrategy.OnPush`.

Verified by: **[ESLint]** `@angular-eslint/prefer-standalone`, `@angular-eslint/prefer-on-push-component-change-detection`, and a restricted-syntax rule on `NgModule`.

---

## FA-007 — Presentational Components Are Pure

**MANDATORY**

Components in `features/*/components` and `shared` receive data through inputs and emit through outputs. They do not inject stores, data-access services or the router.

Verified by: **[ESLint]** boundary rules (`components` may not import `data-access`).

---

## FA-008 — Signal-Based State

**MANDATORY**

Feature state lives in a signal store in `data-access/`, provided on the feature route. Stores expose read-only signals and methods; they do not expose writable signals.

NgRx SignalStore is allowed for complex features. Global NgRx Store (actions, reducers, effects) requires an ADR.

Verified by: review; **[ESLint]** `no-restricted-imports` on `@ngrx/store` and `@ngrx/effects`.

---

## FA-009 — Lazy-Loaded Feature Routes

**MANDATORY**

Each feature is reached through a lazy route (`loadChildren` or `loadComponent`) in `app.routes.ts`. Guards and resolvers are functional.

Verified by: **[ESLint]** boundary rules (only lazy `import()` of features is allowed from `app.routes.ts`); build output shows one chunk per feature.

---

# 3. Forms, UI and Accessibility

## FA-010 — Typed Reactive Forms

**MANDATORY**

Business data entry uses typed reactive forms. Untyped `FormGroup`/`UntypedFormGroup` and template-driven forms (`ngModel`) are not used for business data. Server validation errors are mapped back to controls.

Verified by: **[ESLint]** `no-restricted-imports` on `Untyped*` and `FormsModule` in features.

---

## FA-011 — Design System Compliance

**MANDATORY**

UI is built with Angular Material themed from the company design tokens. Component styles do not hard-code colors. Another UI component library requires an ADR.

Verified by: Stylelint rule forbidding color literals outside `styles/tokens`; dependency allow-list in CI.

---

## FA-012 — Internationalization and Accessibility

**MANDATORY**

All user-visible text is marked for `@angular/localize`. Dates, numbers and currencies use locale-aware pipes.

The application meets WCAG 2.2 AA. Component tests and E2E journeys run axe checks with no serious or critical violations.

Verified by: **[ESLint]** `@angular-eslint/template/i18n` and template accessibility rules; axe assertions in tests.

---

# 4. Security, Performance and Operations

## FA-013 — Browser Security

**MANDATORY**

- Authentication uses OIDC Authorization Code with PKCE through the `core` auth interceptor.
- Tokens are never stored in `localStorage`, and are sent only to the API origin.
- No secrets in source or bundle.
- `bypassSecurityTrust*` and `innerHTML` with untrusted data require an ADR.
- The serving container sets a strict CSP.

Verified by: **[ESLint]** restricted APIs; secret scanning; header check in deployment smoke test.

---

## FA-014 — Performance Budgets

**MANDATORY**

`angular.json` defines at least the budgets in `architecture.md` (initial bundle 800 kB error, lazy chunk 500 kB error, component style 10 kB error). Budgets are not raised without an ADR.

Verified by: **[CI budget]** `ng build` fails when a budget is exceeded.

---

## FA-015 — Testing, Observability and Deployment

**MANDATORY**

- Components and stores have tests with Jest or Vitest and Angular Testing Library.
- Critical journeys are covered by Playwright E2E.
- OpenTelemetry Web and a global `ErrorHandler` are initialized in `core`, propagating `traceparent` and reporting no personal data.
- The application ships as a static container behind the gateway, with runtime `config.json` and one image promoted across environments.

Verified by: CI pipeline stages; review of `core/` and deployment manifests.

---

## FA-016 — Keep Business Rules in the Backend

**RECOMMENDED**

Frontend validation and derived values exist for user experience only. Calculations that decide business outcomes (pricing, eligibility, approvals) are performed by the backend and displayed, not recomputed.

Verified by: review.

---

# Governing Principle

> **A back-office frontend is a thin, fast, accessible client of the Business API: features stay isolated, HTTP stays in data-access, and every checkable rule is checked by the build.**
