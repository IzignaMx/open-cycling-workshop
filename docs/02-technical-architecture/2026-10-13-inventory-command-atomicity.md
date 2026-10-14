# ADR · Inventory command atomicity and reservation finalization

Status: Accepted for V0.2 Increment 2 Task 3, subject to its verification gates.

## Context and precedence

FR-INV-001/002/003/004, FR-SVC-011 and BR-006 require scoped products,
append-only movements, ledger-derived stock, and reservation/consumption tied to
orders. The shipped inventory implementation in commit
`30524e01e1433ecc87d7a75f42c6bd4f46c0e4a1` records an ADR note: RESERVE is `-n`,
RELEASE/CONSUME are `+n` hold finalizations, and physical deductions use signed
ADJUST entries. The implementation-plan shorthand saying CONSUME `-n` conflicts
with that accepted note and the shipped model, so it is corrected here.

Available stock is SUM(quantity). Starting at 10, RESERVE 4 produces 6.
CONSUME alone would wrongly restore 10; changing CONSUME to -4 would wrongly
leave 2. Existing rows must not be rewritten or silently reinterpreted.

## Decision

- Every API movement is a server-authoritative, authenticated online command.
  Organization and actor come from the effective principal; location comes
  from the authorized product. No inventory-movement mutation queue is added.
- RESERVE requires sufficient available stock and an order in the product's
  organization/location. RELEASE restores the held quantity.
- CONSUME atomically inserts the existing `+n` hold-finalization entry and an
  inseparable `ADJUST -n` physical issue. Both carry the same organization,
  location, product, order, reservation reference and timestamp. The companion
  has its own server-generated UUIDv7 and a note linking the command ID.
  Available stock stays at 6 after consuming the example reservation.
- The response represents the original command entry, including its signed
  quantity. Consumers must use the stock endpoint for the net available balance;
  CONSUME's response quantity alone is not the command's net stock delta.
- Finalization is whole-reservation only: exact product/order/reference and
  quantity, with one RELEASE or CONSUME winner. Partial finalization requires a
  separate remaining-quantity specification and is rejected in this increment.
- All public ledger writes lock the product row with PostgreSQL FOR UPDATE.
  After acquiring the lock they check idempotency, stock, references and prior
  finalization. A partial unique database index on organization/reference for
  RELEASE/CONSUME additionally rejects multiple finalizers. The ADJUST companion
  is excluded from this index.
- `movement_id` is a required UUIDv7 idempotency key. Exact normalized replay by
  the same actor returns the original entry without inserting anything. Reusing
  it with a different command/actor yields 409. Retries retain their original
  movement ID. New product IDs default to server-generated UUIDv7.
- ADJUST accepts signed corrections, including a negative result; it is an
  explicit audited correction, never an untracked mutable stock overwrite.
  RESERVE cannot overdraw available stock.
- Product listing requires a location and bounded pagination. SKU remains
  unique per organization as already defined in migration 0006.

## Recovery and compatibility

Migration 0007 adds only the partial unique index. It preflights duplicate
historical terminal references and fails with an actionable message instead of
rewriting/removing ledger rows. Operators must investigate duplicates and use
an explicitly reviewed reconciliation procedure; automatic cleanup is unsafe.
A failed preflight must not be bypassed by deleting financial/inventory history.

Existing historical CONSUME/ADJUST rows remain unchanged. This increment does
not infer missing physical deductions from legacy data or retroactively attach
unlinked adjustments. Such reconciliation needs separate operator evidence.
Downgrading removes the guard index only, not movement records.

SQLite is a functional-test surrogate. Only PostgreSQL contention tests prove
row-lock serialization; SQLite passes are not concurrent correctness evidence.

## Verification

- Full stock lifecycle, duplicate finalization, exact replay and payload reuse.
- Tenant/location/capability rejection and strict input validation.
- Companion-insert failure rolls back both consumption records.
- PostgreSQL contention: competing reserves, RELEASE versus CONSUME, identical
  reservation commands and identical consumption commands.
- Empty migration path and seeded 0006 upgrade preserve all rows and balances;
  duplicate historical finalizations block safely.
- Regenerated OpenAPI and TypeScript types, full static checks and hosted CI.

No UI, quote aggregate, deployment or historic data cleanup is included.
