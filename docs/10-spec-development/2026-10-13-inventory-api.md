# Inventory API · Increment 2 Task 3

Requirements: FR-INV-001/002/003/004, FR-SVC-011, BR-006, deny-by-default scoped
capabilities, strict request schemas and auditable append-only changes.

See the accepted [command atomicity ADR](../02-technical-architecture/2026-10-13-inventory-command-atomicity.md)
for reservation arithmetic, idempotency, concurrent finalization and migration.

## Endpoints and acceptance

- POST `/api/v1/inventory/products`: inventory.write; scoped location, normalized
  SKU/name/unit; generated UUIDv7 or caller-supplied UUIDv7. Duplicate ID/SKU 409.
- GET `/api/v1/inventory/products?location_id=...`: inventory.read; required
  location, limit 1–200 (default 100), offset 0–2147483647, stable name/ID ordering.
- GET `/api/v1/inventory/products/{id}/stock`: inventory.read; derived scoped
  `available_quantity`, never a mutable stock field.
- POST `/api/v1/inventory/movements`: inventory.write; required UUIDv7
  `movement_id`, `product_id`, `kind`, integer `quantity`, optional order/reference
  and note. RESERVE/RELEASE/CONSUME require an order; finalizers require a
  reference. Quantities are positive except signed ADJUST. Responses are 201,
  including exact replay, and return the original ledger command.

Missing authentication is 401, denied capability/location 403, unavailable
cross-tenant/missing objects 404, semantic conflicts 409, and malformed input 422. Extra fields are rejected, preventing client-supplied actor, organization,
location, timestamp or companion entries. Validation must precede any commit.

Stock/read access follows product tenant/location scope. All referenced orders
and reservations must belong to that product's location. Finalization also
requires matching product, order, quantity and RESERVE kind. A command cannot
be replayed as a different actor or with a changed canonical body.

Consumption releases the hold and records physical outflow in one transaction.
If either insertion fails, neither is committed. Product locking and a unique
finalization index prevent concurrent double release/consume; replay is checked
after locking. Out-of-band SQL is not an authorized public write path.

## Evidence and scope

- Repository regression observed red: lookup returned a distinct RELEASE ID
  instead of its reservation reference (1 failed, 4 passed).
- API test observed red: product-create endpoint absent (404 instead of 201).
- Local final ladder: 370 Python tests passed, eight PostgreSQL-dependent tests
  skipped; 160 inventory API cases passed. All 21 runnable aggregate checks passed
  with five explicit environment blockers. Frontend tests, lint/format/mypy,
  contracts, TypeScript checks, HTTP smoke and PWA build passed.
- Independent review found and fixed canonical Unicode SKU-length overflow and
  oversized pagination input. NUL text is rejected at body/query/path boundaries.
  Review also checked locking, replay, atomicity and isolated-schema test safety.
- Exact hosted test results are recorded in the draft PR. PostgreSQL contention,
  seeded migration and browser checks remain pending until a hosted run proves
  them; local SQLite and offline SQL generation do not supply that evidence.
- New migration does not alter historical data; operator reconciliation is
  required if existing terminal duplicates block its preflight.

No main merge/deploy is authorized for this increment. Quote domain (plan Task
4), product/quote sync (Task 7), UI and full quote/inventory E2E (Tasks 10–11)
remain separate work. Physical V0.1 qualification remains open.
