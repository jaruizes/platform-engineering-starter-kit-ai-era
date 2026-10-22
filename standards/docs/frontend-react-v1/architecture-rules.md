# Architecture rules: frontend React v1

## Purpose

These are the verifiable acceptance rules for customer-facing web applications built on the React v1 architecture (React 19, TypeScript, Vite, feature-sliced structure).

They do not restate the architecture. Intent, structure and rationale are in `architecture.md`. Rules shared by all architectures are in `../common/development-rules.md`.

This document answers only:

> **What must be true for a React v1 frontend to be considered architecture-compliant?**

---

# Acceptance Model

Rules are classified as:

- **MANDATORY** — failure means architecture validation is `KO`, unless an approved ADR explicitly authorizes the exception.
- **CONDITIONAL** — mandatory when the described situation exists.
- **RECOMMENDED** — deviation should be justified when material.

Each rule states how it is checked. Rules marked *Enforced by* must fail the CI pipeline when broken:

- **ESLint boundaries** — `eslint-plugin-boundaries` or `steiger`;
- **ESLint** — other lint rules (`no-restricted-imports`, `no-restricted-syntax`, `jsx-a11y`);
- **Bundle budget** — bundle size check on the Vite build;
- **Lighthouse CI** — lab performance and accessibility audits on main pages.

Rules without automated enforcement are checked in review.

---

# 1. Structure

## FR-001 — Feature-Sliced Layers

**MANDATORY**

Source code is organized in the layers `app/`, `pages/`, `features/`, `entities/` and `shared/`. Features use the segments `ui/`, `model/` and `api/` when needed. No other top-level folders under `src/` except test setup.

*Enforced by:* ESLint boundaries (unknown files are reported).

---

## FR-002 — Import Direction

**MANDATORY**

Imports follow `app → pages → features → entities → shared`. A layer never imports from a layer to its left. Slices on the same layer (two features, two entities, two pages) do not import each other.

*Enforced by:* ESLint boundaries.

---

## FR-003 — Public API per Slice

**MANDATORY**

Each slice exposes what it shares through its `index.ts`. Imports from outside the slice target the slice root, never internal paths such as `features/checkout/ui/Summary`.

*Enforced by:* ESLint boundaries (entry-point rule).

---

## FR-004 — Strict TypeScript

**MANDATORY**

`tsconfig` has `strict: true` and `noUncheckedIndexedAccess: true`. `any` and `@ts-ignore` are not allowed; `@ts-expect-error` needs a comment.

*Enforced by:* `tsc --noEmit` and ESLint (`@typescript-eslint/no-explicit-any`, `ban-ts-comment`).

---

# 2. Data and State

## FR-005 — Backend Access Only Through the Generated Client

**MANDATORY**

The frontend calls only the Business API or the team's BFF, through the client generated from the OpenAPI contract in `shared/api/generated`. Hand-written `fetch`/`axios` calls to backend endpoints, and direct access to databases, topics or internal services, are not allowed. Generated files are not edited by hand.

*Enforced by:* ESLint (`no-restricted-globals`/`no-restricted-imports` for `fetch` and `axios` outside `shared/api`) and a CI check that regenerating the client produces no diff.

---

## FR-006 — Server State with TanStack Query

**MANDATORY**

Backend data is read and written with TanStack Query hooks located in an `api/` segment. Server data is not copied into `useState`, context or a global store. Mutations invalidate or update the affected queries.

*Enforced by:* review; ESLint `@tanstack/eslint-plugin-query`.

---

## FR-007 — Global Client State Is Justified

**CONDITIONAL** — applies when a global store exists.

Global client state uses Zustand only, holds no server data, and each store file states why local, URL or context state is not enough. Redux and other state libraries are not allowed.

*Enforced by:* ESLint (`no-restricted-imports`) and review.

---

## FR-008 — Forms with React Hook Form and Zod

**CONDITIONAL** — applies to every form with validation.

Forms use React Hook Form with a Zod schema in the feature `model/` segment. Form types come from `z.infer`. Server validation errors are mapped to fields.

*Enforced by:* review.

---

# 3. Routing and Performance

## FR-009 — Lazy Routes

**MANDATORY**

The app uses a React Router data router. Every page route is loaded with the route `lazy` property or `React.lazy`. Only `app/` and the shell are in the entry chunk.

*Enforced by:* review and bundle budget (entry chunk size).

---

## FR-010 — Performance Budgets

**MANDATORY**

Main pages meet LCP < 2.5 s, INP < 200 ms and CLS < 0.1 at the 75th percentile in real user monitoring. In CI, Lighthouse CI fails on lab budgets (LCP, total blocking time, CLS) and the bundle check fails when a route exceeds its JavaScript budget (default 170 KB gzip initial, 60 KB gzip per lazy route).

*Enforced by:* Lighthouse CI and bundle budget.

---

## FR-011 — SSR or Static Rendering Requires an ADR

**CONDITIONAL** — applies when server rendering or prerendering is introduced.

An approved ADR documents the SEO or performance need, the chosen option and its operational impact. Rules FR-001 to FR-010 still apply.

*Enforced by:* review.

---

# 4. UI, Accessibility and Language

## FR-012 — Design System Only

**MANDATORY**

UI uses the company design system components and tokens. No other CSS or component framework is installed. Colors, spacing and typography use tokens, not literal values.

*Enforced by:* ESLint (`no-restricted-imports`), dependency allowlist and Stylelint (no literal colors).

---

## FR-013 — Accessibility WCAG 2.2 AA

**MANDATORY**

Pages meet WCAG 2.2 AA. No `jsx-a11y` errors, no axe violations of level A or AA in component and E2E tests, and a Lighthouse accessibility score of at least 95 on main pages. Critical journeys are checked manually with keyboard and screen reader before release.

*Enforced by:* ESLint (`jsx-a11y`), axe in tests, Lighthouse CI.

---

## FR-014 — Internationalized Text

**MANDATORY**

User-visible text goes through i18next. Dates, numbers and amounts use `Intl` with the active locale. No literal strings in JSX except for non-translatable symbols.

*Enforced by:* ESLint (`i18next/no-literal-string`).

---

# 5. Security

## FR-015 — Browser Security Baseline

**MANDATORY**

- Authentication uses OIDC Authorization Code with PKCE.
- Tokens and personal data are never stored in `localStorage` or `sessionStorage`.
- `dangerouslySetInnerHTML` is not used, unless an ADR approves a single sanitizing wrapper.
- The serving layer sends a CSP without `unsafe-inline` or `unsafe-eval` for scripts.
- No secrets in `VITE_*` variables or the bundle.

*Enforced by:* ESLint (`react/no-danger`, `no-restricted-properties` for storage APIs), header check in the deployment smoke test, and secret scanning.

---

# 6. Quality and Operations

## FR-016 — Test Strategy

**MANDATORY**

Components and hooks are tested with Vitest and React Testing Library. Network calls in tests are mocked with MSW, not by mocking the client module. Critical journeys have Playwright E2E tests. Coverage thresholds follow the common testing standard.

*Enforced by:* CI test stage and coverage thresholds.

---

## FR-017 — Observability

**MANDATORY**

The app initializes OpenTelemetry Web with trace propagation to the Business API, reports unhandled errors and error boundary events with private source maps, and sends Core Web Vitals to real user monitoring. Telemetry contains no personal data.

*Enforced by:* review and deployment smoke test.

---

## FR-018 — Immutable Static Bundle

**RECOMMENDED**

The same build is promoted across environments with runtime configuration from `config.json`. Hashed assets are cached long term; `index.html` is not cached.

*Enforced by:* review.
