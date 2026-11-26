# Retail demo fixture

Synthetic, deterministic and intentionally free of personal data. **Not customer data.**

- `V1__create_sales_schema.sql`: Flyway DDL.
- `V2__seed_demo_sales.sql`: ready-to-apply Flyway SQL for products, stores and sales.
- `sales.csv`: inspectable equivalent of the SQL `sales` rows; SQL is the runtime import.
- `retail-operations.json`: approved REST paths and typed query parameters for Spec 02.

Rows: **12 products**, **3 stores**, **196 sales**.
Period: **2026-10-26 to 2026-11-22**, inclusive.

## Golden fixture assertions

| Period | Transactions | Units | Revenue (cents) |
|---|---:|---:|---:|
| 2026-11-09 to 2026-11-15 | 49 | 160 | 86460 |
| 2026-11-16 to 2026-11-22 | 49 | 169 | 91641 |

The backend REST contract returns `revenueCents` as an integer; display as EUR only after dividing by 100. No timezone assumptions: `sold_at` is a SQL DATE.

Copy both SQL migrations into the Spring service's `src/main/resources/db/migration/` before its first production deployment. If the demo database was previously initialized, create a **new ephemeral environment**, rather than rewriting an already executed Flyway migration.
