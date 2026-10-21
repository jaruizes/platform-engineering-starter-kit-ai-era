# Examples: frontend Angular v1

## Purpose

Short, compliant code examples for the Angular v1 back-office architecture, plus common non-compliant patterns and how to fix them, each tied to an FA rule.

The examples use a hypothetical `orders` feature. They are illustrations of `architecture.md` and `architecture-rules.md`, not a template; start real applications from the platform template.

---

# 1. Data-access service wrapping the generated client

`OrdersApi` and `OrderDto` are generated into `src/app/api/` (FA-005). The service maps DTOs to view models and is the only HTTP entry point of the feature (FA-003).

```typescript
// features/orders/data-access/orders.service.ts
@Injectable({ providedIn: 'root' })
export class OrdersService {
  private readonly api = inject(OrdersApi);

  search(filter: OrderFilter): Observable<Page<OrderRow>> {
    return this.api
      .searchOrders(filter.status, filter.page, filter.size)
      .pipe(map((res) => ({ total: res.total, items: res.items.map(toOrderRow) })));
  }
}
```

---

# 2. Signal store

Provided on the feature route, exposes read-only signals and methods (FA-008).

```typescript
// features/orders/data-access/orders.store.ts
@Injectable()
export class OrdersStore {
  private readonly service = inject(OrdersService);
  private readonly state = signal<{ items: OrderRow[]; loading: boolean }>({ items: [], loading: false });

  readonly items = computed(() => this.state().items);
  readonly loading = computed(() => this.state().loading);

  load(filter: OrderFilter): void {
    this.state.update((s) => ({ ...s, loading: true }));
    this.service.search(filter).subscribe({
      next: (page) => this.state.set({ items: page.items, loading: false }),
      error: () => this.state.update((s) => ({ ...s, loading: false })),
    });
  }
}
```

---

# 3. Standalone OnPush page

```typescript
// features/orders/pages/orders-page.component.ts
@Component({
  selector: 'app-orders-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [OrdersTableComponent, MatProgressBar],
  template: `
    <h1 i18n>Orders</h1>
    @if (store.loading()) { <mat-progress-bar mode="indeterminate" /> }
    <app-orders-table [rows]="store.items()" (open)="openOrder($event)" />
  `,
})
export class OrdersPageComponent {
  protected readonly store = inject(OrdersStore);
  private readonly router = inject(Router);
  readonly status = input<OrderStatus>('OPEN'); // bound from the query string

  constructor() {
    effect(() => this.store.load({ status: this.status(), page: 0, size: 50 }));
  }

  openOrder(id: string): void {
    this.router.navigate(['/orders', id]);
  }
}
```

`OrdersTableComponent` only has `input()` and `output()` (FA-007).

---

# 4. Lazy route

```typescript
// app.routes.ts
export const routes: Routes = [
  {
    path: 'orders',
    canActivate: [hasRole('orders.read')],
    loadChildren: () => import('./features/orders/orders.routes').then((m) => m.ORDER_ROUTES),
  },
];

// features/orders/orders.routes.ts
export const ORDER_ROUTES: Routes = [
  { path: '', providers: [OrdersStore], component: OrdersPageComponent },
];
```

---

# 5. Typed reactive form

```typescript
// features/orders/components/order-form.component.ts
export class OrderFormComponent {
  private readonly fb = inject(NonNullableFormBuilder);

  readonly form = this.fb.group({
    customerId: ['', Validators.required],
    quantity: [1, [Validators.required, Validators.min(1)]],
    comment: ['', Validators.maxLength(500)],
  });

  readonly submitted = output<OrderDraft>();

  submit(): void {
    if (this.form.valid) this.submitted.emit(this.form.getRawValue()); // typed OrderDraft
  }
}
```

---

# 6. ESLint boundaries excerpt

Enforces FA-002, FA-003 and FA-007.

```js
// eslint.config.js (excerpt)
settings: {
  'boundaries/elements': [
    { type: 'core', pattern: 'src/app/core/**' },
    { type: 'shared', pattern: 'src/app/shared/**' },
    { type: 'api', pattern: 'src/app/api/**' },
    { type: 'page', pattern: 'src/app/features/*/pages/**', capture: ['feature'] },
    { type: 'component', pattern: 'src/app/features/*/components/**', capture: ['feature'] },
    { type: 'data-access', pattern: 'src/app/features/*/data-access/**', capture: ['feature'] },
    { type: 'model', pattern: 'src/app/features/*/models/**', capture: ['feature'] },
  ],
},
rules: {
  'boundaries/element-types': ['error', {
    default: 'disallow',
    rules: [
      { from: 'page', allow: [['component', { feature: '${from.feature}' }], ['data-access', { feature: '${from.feature}' }], ['model', { feature: '${from.feature}' }], 'shared', 'core'] },
      { from: 'component', allow: [['component', { feature: '${from.feature}' }], ['model', { feature: '${from.feature}' }], 'shared'] },
      { from: 'data-access', allow: [['model', { feature: '${from.feature}' }], 'api', 'core'] },
      { from: 'shared', allow: ['shared'] },
      { from: 'core', allow: ['core', 'shared', 'api'] },
    ],
  }],
}
```

---

# 7. Component test

```typescript
// features/orders/components/order-form.component.spec.ts
it('emits a typed draft when the form is valid', async () => {
  const submitted = jest.fn();
  await render(OrderFormComponent, { on: { submitted } });

  await userEvent.type(screen.getByLabelText(/customer/i), 'C-42');
  await userEvent.click(screen.getByRole('button', { name: /save/i }));

  expect(submitted).toHaveBeenCalledWith({ customerId: 'C-42', quantity: 1, comment: '' });
});
```

With Vitest, replace `jest.fn()` with `vi.fn()`.

---

# 8. Non-compliant examples

## 8.1 Component calling HTTP directly

```typescript
// features/orders/components/orders-table.component.ts
export class OrdersTableComponent {
  private readonly http = inject(HttpClient);
  rows = toSignal(this.http.get<OrderDto[]>('/api/orders'));
}
```

**Why:** violates FA-003 (HTTP outside data-access), FA-005 (hand-written call instead of generated client) and FA-007 (presentational component fetches its own data). ESLint fails the build.

**Fix:** move the call to `OrdersService` using `OrdersApi`, expose it through `OrdersStore`, and give the table an `input<OrderRow[]>()`.

## 8.2 Feature importing another feature

```typescript
// features/invoices/pages/invoice-page.component.ts
import { OrdersStore } from '../../orders/data-access/orders.store';
```

**Why:** violates FA-002. Features become coupled and can no longer be loaded, changed or tested independently.

**Fix:** the invoices feature gets what it needs from its own data-access service calling the Business API. If only a UI piece is shared, move it to `shared/ui`.

## 8.3 NgModule and default change detection

```typescript
@NgModule({ declarations: [OrdersPageComponent], imports: [CommonModule] })
export class OrdersModule {}

@Component({ selector: 'app-orders-page', templateUrl: './orders-page.html' })
export class OrdersPageComponent {}
```

**Why:** violates FA-006 (NgModule, missing OnPush) and usually FA-009 (module-based routing instead of a lazy feature route).

**Fix:** delete the module, make the component standalone with `ChangeDetectionStrategy.OnPush`, and declare it in `orders.routes.ts` loaded through `loadChildren`.
