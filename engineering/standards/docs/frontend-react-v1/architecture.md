# Frontend architecture: React v1

## Purpose

React v1 is the reference architecture for customer-facing web applications: public, high-traffic, performance-sensitive and SEO-sensitive frontends built with React 19, TypeScript and Vite and served as a static bundle behind the gateway.

This document describes the intended structure, technology choices and rationale. The verifiable acceptance criteria are in `architecture-rules.md` (rules `FR-xxx`). Code-level rules shared by every architecture (simplicity, naming, error handling, secrets, dependencies, generated code) are in `../common/development-rules.md` and are not repeated here.

---

## When to use it

Use React v1 when the application:

- is used by customers or anonymous visitors on the public internet;
- has strict performance goals (Core Web Vitals) or depends on search engine visibility;
- must handle high and spiky traffic, served mainly from a CDN;
- has a product-driven UX that changes often.

Use the Angular architecture (`frontend-angular-v1`) instead for internal back-office applications: authenticated staff tools, data-heavy forms and tables, long-lived screens where SEO and first-load performance do not matter and a more opinionated framework is preferred.

Do not mix both architectures in the same application. A customer-facing app that needs server-side rendering or static generation (for example a content-heavy marketing area) may use an SSR or SSG option only with an approved ADR; the folder structure, layering and rules in this document still apply.

---

## Folder structure and import direction

Applications use a feature-sliced structure:

```text
src/
├── app/            # bootstrap, providers, router, global styles, error boundary
├── pages/          # one folder per route; composes features and entities
│   └── order-history/
├── features/       # user-facing capabilities
│   └── <feature>/
│       ├── ui/     # components of the feature
│       ├── model/  # hooks, local state, schemas, business-free UI logic
│       └── api/    # TanStack Query hooks over the generated client
├── entities/       # business entities shown in many places (customer, order)
│   └── order/
│       ├── ui/
│       └── model/
└── shared/
    ├── ui/         # thin wrappers over the design system
    ├── lib/        # framework-agnostic helpers (formatting, dates, money)
    └── api/        # generated OpenAPI client, HTTP instance, query client
```

Imports go in one direction only:

```text
app → pages → features → entities → shared
```

A layer may import from any layer to its right, never to its left. Slices on the same layer do not import each other: `features/checkout` must not import `features/cart`. When two features need the same thing, move it down to `entities` or `shared`, or compose them in a page.

Each slice exposes a public API through an `index.ts`. Other layers import from the slice root (`@/features/checkout`), never from its internal files. The direction and the public API are enforced by ESLint (`eslint-plugin-boundaries` or `steiger`) in CI.

---

## Components

- Function components and hooks only. No class components.
- A component renders and handles user events. Data fetching lives in `api/` hooks; derived logic lives in `model/` hooks or pure functions.
- Props are typed explicitly. No `any`; TypeScript runs with `strict: true` and `noUncheckedIndexedAccess`.
- Keep components small. Split when a component mixes layout, data and complex interaction.
- Business rules belong to the backend. The frontend formats, validates input for usability and shows state; it does not decide prices, eligibility or permissions.
- Each page has an error boundary and a loading state. Use React `Suspense` for lazy routes and data where it makes the code simpler.

---

## State: server versus client

Separate the two kinds of state.

**Server state** is data owned by the backend: orders, products, the customer profile. It is managed only with TanStack Query: queries for reads, mutations for writes, invalidation after mutations. Do not copy server data into a client store. Query keys are defined next to the hooks in `features/<feature>/api` or `entities/<entity>/api`, with a factory per resource.

**Client state** is UI state the backend does not know about: an open dialog, a selected tab, a filter not yet applied.

- Prefer local state (`useState`, `useReducer`) in the component that owns it.
- Put shareable state in the URL (search params) when it should survive a reload or be linkable, such as filters and pagination.
- Use React context for rarely changing values (theme, locale).
- Use a global store (Zustand) only when several distant parts of the UI share state that changes often and is not server data. Record the reason in the store file. Redux is not part of this architecture.

---

## Routing and code splitting

Routing uses React Router with a data router (`createBrowserRouter`). Every page route is lazy-loaded with the `lazy` route property, so each page is its own chunk. Route loaders may prefetch TanStack Query data (`queryClient.ensureQueryData`) to start requests in parallel with the chunk download.

Rules of thumb:

- One route folder in `pages/` per route.
- Heavy components that are not visible at first render (charts, maps, rich editors) are split with `React.lazy`.
- Routes that need authentication are guarded in the router, not inside each component.
- Static rendering or SSR (for example React Router framework mode or a static prerender step) requires an ADR that explains the SEO or performance need.

---

## Talking to the backend

The frontend talks only to the Business API exposed through the gateway, or to an optional BFF owned by the same team. It never calls databases, message topics, internal services or third-party back-office APIs directly.

The HTTP client is generated from the backend OpenAPI contract with orval or openapi-typescript and lives in `shared/api/generated`. Generated files are not edited by hand; regenerate them when the contract changes and commit the contract version used. Hand-written `fetch` or `axios` calls to backend endpoints are not allowed.

Errors follow the backend error model (RFC 9457 problem details). A single HTTP layer in `shared/api` adds the access token, correlation headers and maps errors to typed results. Components show user-facing messages, never raw server messages or stack traces.

---

## Forms and validation

Forms use React Hook Form with a Zod schema through `@hookform/resolvers/zod`. The schema lives in the feature `model/` folder and is the single source of the form's types (`z.infer`). Where the OpenAPI contract already defines the payload, generate the Zod schema with orval or keep it aligned with the generated types.

Client validation exists for usability. The backend validates again and remains the authority. Server validation errors are mapped back to fields with `setError`.

---

## UI and design system

All UI is built with the company design system: design tokens (colors, spacing, typography, radius) and accessible primitives based on Radix. Do not add another CSS or component framework (Bootstrap, Tailwind, Material UI, Chakra) and do not hard-code colors or spacing values that exist as tokens.

`shared/ui` may contain thin wrappers around design system components when the app needs a variant. If a component is useful to several applications, contribute it to the design system instead of growing a local copy. Styling uses CSS Modules or the styling approach the design system ships with.

---

## Security

- Authentication uses OIDC Authorization Code flow with PKCE through the company identity provider. Prefer a BFF or gateway session with secure, `HttpOnly`, `SameSite` cookies; if tokens are held by the browser, keep them in memory only.
- Never store tokens or personal data in `localStorage` or `sessionStorage`.
- A strict Content Security Policy is set by the serving layer: no `unsafe-inline` scripts, no `unsafe-eval`, explicit `connect-src` for the API origins.
- Do not use `dangerouslySetInnerHTML`. If rich content must be rendered, an ADR approves a sanitizer (DOMPurify) and a single wrapper component.
- No secrets in the bundle. Every `VITE_*` variable is public by definition.
- Dependencies are scanned in CI; see the common technology policy.

---

## Internationalization and accessibility

All user-visible text goes through i18next (`react-i18next`). No hard-coded strings in components. Translation files live per feature or per locale and are loaded lazily. Dates, numbers and money use `Intl` formatters with the active locale.

Applications meet WCAG 2.2 level AA:

- use semantic HTML and the design system primitives, which handle focus and ARIA;
- every interactive element is reachable and usable with the keyboard, with a visible focus;
- images have meaningful `alt` text; form fields have labels and announced errors;
- color contrast follows the tokens, which are designed to pass AA.

Automated checks run with `eslint-plugin-jsx-a11y` and axe (in component tests and Playwright). Automated checks do not replace a manual keyboard and screen reader review of key journeys.

---

## Performance budgets

Customer-facing apps are measured on the field metrics (Core Web Vitals, 75th percentile):

| Metric | Budget |
|---|---|
| Largest Contentful Paint (LCP) | < 2.5 s |
| Interaction to Next Paint (INP) | < 200 ms |
| Cumulative Layout Shift (CLS) | < 0.1 |

Each route also has a JavaScript budget (default: 170 KB gzip for the initial route including shared chunks, 60 KB gzip per additional lazy route), set in the bundle size check. Lighthouse CI runs on the main pages for every pull request and fails when budgets are exceeded.

Techniques: lazy routes, modern image formats with explicit sizes, preloading the LCP image and critical fonts, avoiding large dependencies (check with the bundle analyzer), and avoiding layout shift by reserving space for async content.

---

## Testing

The common testing standard applies. For this architecture:

- **Unit and component tests** with Vitest and React Testing Library. Test behavior as the user sees it (roles, labels, text), not implementation details.
- **API mocking** with MSW at the network level. Handlers are built from the OpenAPI contract types so mocks stay aligned with the backend.
- **End-to-end** with Playwright for a few critical journeys only (for example sign-in, search, checkout), run against a deployed environment.
- **Accessibility** checks with axe in component tests and E2E.

---

## Observability

- OpenTelemetry Web SDK for traces of document load and fetch calls; the `traceparent` header is propagated to the Business API so a user action can be followed into the backend.
- An error reporting tool captures unhandled errors and error boundary events, with source maps uploaded at build time (never served publicly).
- Real user monitoring collects Core Web Vitals with the `web-vitals` library per route.
- No personal data in telemetry. Mask user input and identifiers.

---

## Build and deployment

Vite builds a static bundle with hashed file names. The bundle is packaged into a small container image (for example nginx-unprivileged) or published to the CDN, and served behind the API gateway on the same site as the Business API to avoid CORS where possible.

- `index.html` is not cached; hashed assets are cached for a long time.
- Runtime configuration (API base URL, OIDC client id, telemetry endpoint) is loaded from a `config.json` served per environment, so the same bundle is promoted across environments.
- The serving layer sets security headers (CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy`).
- The CI pipeline runs type check, lint (including boundaries), tests, bundle budget and Lighthouse CI before the image is published.
