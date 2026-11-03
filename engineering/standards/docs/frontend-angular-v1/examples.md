# Examples: frontend Angular v1

## Purpose

Short, compliant code examples for the Angular v1 architecture, plus common non-compliant patterns and how to fix them, each tied to an FA rule.

The examples use a hypothetical `records` feature. They are illustrations of `architecture.md` and `architecture-rules.md`, not a template; start real applications from the platform template.

---

# 1. Data-access service wrapping the generated client

`RecordsApi` and `RecordDto` are generated into `src/app/api/` (FA-005). The service maps DTOs to view models and is the only HTTP entry point of the feature (FA-003).

```typescript
// features/records/data-access/records.service.ts
@Injectable({ providedIn: 'root' })
export class RecordsService {
  private readonly api = inject(RecordsApi);

  search(filter: RecordFilter): Observable<Page<RecordRow>> {
    return this.api
      .searchRecords(filter.status, filter.page, filter.size)
      .pipe(map((res) => ({ total: res.total, items: res.items.map(toRecordRow) })));
  }
}
```

---

# 2. Signal store

Provided on the feature route, exposes read-only signals and methods (FA-008).

```typescript
// features/records/data-access/records.store.ts
@Injectable()
export class RecordsStore {
  private readonly service = inject(RecordsService);
  private readonly state = signal<{ items: RecordRow[]; loading: boolean }>({ items: [], loading: false });

  readonly items = computed(() => this.state().items);
  readonly loading = computed(() => this.state().loading);

  load(filter: RecordFilter): void {
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
// features/records/pages/records-page.component.ts
@Component({
  selector: 'app-records-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RecordsTableComponent, MatProgressBar],
  template: `
    <h1 i18n>Records</h1>
    @if (store.loading()) { <mat-progress-bar mode="indeterminate" /> }
    <app-records-table [rows]="store.items()" (open)="openRecord($event)" />
  `,
})
export class RecordsPageComponent {
  protected readonly store = inject(RecordsStore);
  private readonly router = inject(Router);
  readonly status = input<RecordStatus>('OPEN'); // bound from the query string

  constructor() {
    effect(() => this.store.load({ status: this.status(), page: 0, size: 50 }));
  }

  openRecord(id: string): void {
    this.router.navigate(['/records', id]);
  }
}
```

`RecordsTableComponent` only has `input()` and `output()` (FA-007).

---

# 4. Lazy route

```typescript
// app.routes.ts
export const routes: Routes = [
  {
    path: 'records',
    canActivate: [hasRole('records.read')],
    loadChildren: () => import('./features/records/records.routes').then((m) => m.ORDER_ROUTES),
  },
];

// features/records/records.routes.ts
export const ORDER_ROUTES: Routes = [
  { path: '', providers: [RecordsStore], component: RecordsPageComponent },
];
```

---

# 5. Typed reactive form

```typescript
// features/records/components/record-form.component.ts
export class RecordFormComponent {
  private readonly fb = inject(NonNullableFormBuilder);

  readonly form = this.fb.group({
    ownerId: ['', Validators.required],
    quantity: [1, [Validators.required, Validators.min(1)]],
    comment: ['', Validators.maxLength(500)],
  });

  readonly submitted = output<RecordDraft>();

  submit(): void {
    if (this.form.valid) this.submitted.emit(this.form.getRawValue()); // typed RecordDraft
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
// features/records/components/record-form.component.spec.ts
it('emits a typed draft when the form is valid', async () => {
  const submitted = jest.fn();
  await render(RecordFormComponent, { on: { submitted } });

  await userEvent.type(screen.getByLabelText(/owner/i), 'C-42');
  await userEvent.click(screen.getByRole('button', { name: /save/i }));

  expect(submitted).toHaveBeenCalledWith({ ownerId: 'C-42', quantity: 1, comment: '' });
});
```

With Vitest, replace `jest.fn()` with `vi.fn()`.

---

# 8. Non-compliant examples

## 8.1 Component calling HTTP directly

```typescript
// features/records/components/records-table.component.ts
export class RecordsTableComponent {
  private readonly http = inject(HttpClient);
  rows = toSignal(this.http.get<RecordDto[]>('/api/records'));
}
```

**Why:** violates FA-003 (HTTP outside data-access), FA-005 (hand-written call instead of generated client) and FA-007 (presentational component fetches its own data). ESLint fails the build.

**Fix:** move the call to `RecordsService` using `RecordsApi`, expose it through `RecordsStore`, and give the table an `input<RecordRow[]>()`.

## 8.2 Feature importing another feature

```typescript
// features/related/pages/related-page.component.ts
import { RecordsStore } from '../../records/data-access/records.store';
```

**Why:** violates FA-002. Features become coupled and can no longer be loaded, changed or tested independently.

**Fix:** the related feature gets what it needs from its own data-access service calling the approved API contract. If only a UI piece is shared, move it to `shared/ui`.

## 8.3 NgModule and default change detection

```typescript
@NgModule({ declarations: [RecordsPageComponent], imports: [CommonModule] })
export class RecordsModule {}

@Component({ selector: 'app-records-page', templateUrl: './records-page.html' })
export class RecordsPageComponent {}
```

**Why:** violates FA-006 (NgModule, missing OnPush) and usually FA-009 (module-based routing instead of a lazy feature route).

**Fix:** delete the module, make the component standalone with `ChangeDetectionStrategy.OnPush`, and declare it in `records.routes.ts` loaded through `loadChildren`.
