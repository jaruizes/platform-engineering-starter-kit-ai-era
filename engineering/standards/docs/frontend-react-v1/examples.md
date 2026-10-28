# Examples: frontend React v1

## Purpose

Short, compliant code examples for the React v1 customer-facing web architecture, plus common mistakes with the rule they break and how to fix them.

Examples are illustrative. The rules in `architecture-rules.md` are the reference.

---

## Feature component with a TanStack Query hook

The hook wraps the client generated from the OpenAPI contract (FR-005, FR-006).

```ts
// features/order-history/api/useOrders.ts
import { useQuery } from '@tanstack/react-query';
import { listOrders } from '@/shared/api';

export const orderKeys = {
  all: ['orders'] as const,
  list: (page: number) => [...orderKeys.all, 'list', page] as const,
};

export function useOrders(page: number) {
  return useQuery({
    queryKey: orderKeys.list(page),
    queryFn: () => listOrders({ page, size: 20 }),
  });
}
```

```tsx
// features/order-history/ui/OrderList.tsx
import { useTranslation } from 'react-i18next';
import { Alert, Skeleton } from '@/shared/ui';
import { OrderCard } from '@/entities/order';
import { useOrders } from '../api/useOrders';

export function OrderList({ page }: { page: number }) {
  const { t } = useTranslation('orders');
  const { data, isPending, isError } = useOrders(page);

  if (isPending) return <Skeleton rows={5} />;
  if (isError) return <Alert tone="error">{t('loadError')}</Alert>;

  return (
    <ul aria-label={t('listLabel')}>
      {data.items.map((order) => (
        <li key={order.id}><OrderCard order={order} /></li>
      ))}
    </ul>
  );
}
```

---

## Lazy route

Each page is its own chunk (FR-009). The loader starts the request in parallel with the chunk.

```tsx
// app/router.tsx
import { createBrowserRouter } from 'react-router';
import { queryClient } from '@/shared/api';
import { RootLayout } from './RootLayout';

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: 'orders',
        lazy: async () => {
          const { OrderHistoryPage, loader } = await import('@/pages/order-history');
          return { Component: OrderHistoryPage, loader: loader(queryClient) };
        },
      },
    ],
  },
]);
```

---

## Form with React Hook Form and Zod

The schema is the single source of types (FR-008). Messages are translation keys (FR-014).

```tsx
// features/newsletter/model/schema.ts
import { z } from 'zod';

export const subscribeSchema = z.object({
  email: z.string().email('newsletter:errors.email'),
  consent: z.literal(true, { errorMap: () => ({ message: 'newsletter:errors.consent' }) }),
});
export type SubscribeForm = z.infer<typeof subscribeSchema>;
```

```tsx
// features/newsletter/ui/SubscribeForm.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { Button, Checkbox, TextField } from '@/shared/ui';
import { subscribeSchema, type SubscribeForm } from '../model/schema';
import { useSubscribe } from '../api/useSubscribe';

export function SubscribeForm() {
  const { t } = useTranslation('newsletter');
  const subscribe = useSubscribe();
  const { register, handleSubmit, formState: { errors } } =
    useForm<SubscribeForm>({ resolver: zodResolver(subscribeSchema) });

  return (
    <form onSubmit={handleSubmit((values) => subscribe.mutate(values))} noValidate>
      <TextField label={t('email')} error={errors.email && t(errors.email.message!)} {...register('email')} />
      <Checkbox label={t('consent')} error={errors.consent && t(errors.consent.message!)} {...register('consent')} />
      <Button type="submit" loading={subscribe.isPending}>{t('submit')}</Button>
    </form>
  );
}
```

---

## ESLint boundaries config excerpt

Enforces FR-001, FR-002 and FR-003.

```js
// eslint.config.js (excerpt)
import boundaries from 'eslint-plugin-boundaries';

export default [{
  plugins: { boundaries },
  settings: {
    'boundaries/elements': [
      { type: 'app', pattern: 'src/app' },
      { type: 'pages', pattern: 'src/pages/*', capture: ['slice'] },
      { type: 'features', pattern: 'src/features/*', capture: ['slice'] },
      { type: 'entities', pattern: 'src/entities/*', capture: ['slice'] },
      { type: 'shared', pattern: 'src/shared/*' },
    ],
  },
  rules: {
    'boundaries/no-unknown-files': 'error',
    'boundaries/entry-point': ['error', { default: 'disallow',
      rules: [{ target: ['pages', 'features', 'entities', 'shared'], allow: 'index.ts' }] }],
    'boundaries/element-types': ['error', { default: 'disallow', rules: [
      { from: 'app', allow: ['pages', 'features', 'entities', 'shared'] },
      { from: 'pages', allow: ['features', 'entities', 'shared'] },
      { from: 'features', allow: ['entities', 'shared'] },
      { from: 'entities', allow: ['shared'] },
      { from: 'shared', allow: ['shared'] },
    ] }],
  },
}];
```

---

## Component test with MSW

The network is mocked, not the client module (FR-016).

```tsx
// features/order-history/ui/OrderList.test.tsx
import { http, HttpResponse } from 'msw';
import { screen } from '@testing-library/react';
import { server } from '@/shared/test/server';
import { renderWithProviders } from '@/shared/test/render';
import { OrderList } from './OrderList';

it('shows an error when orders cannot be loaded', async () => {
  server.use(http.get('*/api/orders', () => HttpResponse.json({}, { status: 503 })));

  renderWithProviders(<OrderList page={0} />);

  expect(await screen.findByRole('alert')).toHaveTextContent('orders:loadError');
});
```

---

## Non-compliant examples

### 1. Hand-written fetch copied into local state

```tsx
// Non-compliant
const [orders, setOrders] = useState<any[]>([]);
useEffect(() => {
  fetch('/api/orders').then((r) => r.json()).then(setOrders);
}, []);
```

**Why:** bypasses the generated client (FR-005), duplicates server state outside TanStack Query (FR-006), uses `any` (FR-004), and has no loading or error state.

**Fix:** use the `useOrders` hook shown above, built on the generated `listOrders` function.

### 2. Feature importing another feature's internals

```ts
// features/checkout/ui/Summary.tsx — non-compliant
import { CartLine } from '@/features/cart/ui/CartLine';
```

**Why:** a feature imports another feature on the same layer (FR-002) and reaches into an internal path (FR-003). ESLint boundaries fails the build.

**Fix:** move `CartLine` to `entities/cart` and export it from its `index.ts`, or compose cart and checkout in the page.

### 3. Token in localStorage and raw HTML

```tsx
// Non-compliant
localStorage.setItem('access_token', token);
<div dangerouslySetInnerHTML={{ __html: product.description }} />
```

**Why:** tokens in browser storage are readable by any injected script, and unsanitized HTML opens an XSS path (FR-015).

**Fix:** use the BFF session cookie or keep the token in memory in the auth module; render the description as text, or through the ADR-approved sanitizing wrapper if rich text is required.
