# Inventory server module

Inventory commands retain their append-only ledger and accepted reservation
semantics. The connected-read slice adds movement visibility without changing
commands, stored history, SQL0011, grants, write admission or offline protocols.

## Connected reads

- `GET /api/v1/inventory/products` retains the existing location-scoped bare
  product array and bounded limit/offset pagination.
- `GET /api/v1/inventory/products/{product_id}/stock` retains the four-field
  response. Available quantity is the full scoped ledger sum and may be negative.
- `GET /api/v1/inventory/products/{product_id}/movements` returns a page containing
  only movement ID, product ID, organization ID, location ID, kind, signed quantity
  and occurrence time. It never selects actor, order, reservation reference or
  note columns. Additional grants do not expand this projection.

The new route permits only `limit` (1–100, default 50) and `before`, without
repeated keys. A canonical, scope-bound cursor uses exact six-digit UTC timestamps
and Unicode-scalar IDs. Ordering and the continuation predicate both use binary
ID collation (`C` on PostgreSQL). Fetching limit + 1 determines whether another
page exists; a continuation identifies the last returned row. This is live
paging: newer inserts require a refresh; older inserts can appear on later pages.
A cursor is a position, never authorization or a snapshot.

## Read boundary and operational limits

All three reads use the function-scoped `inventory_read_dependency`. It validates
the signed session, installs transaction-local budgets before authority SQL,
acquires the organization then current-actor locks, intersects literal incoming
and current grants, and verifies `inventory.read` and scope. Locks remain held
through DTO materialization and final signed-expiry checking. Reads roll back;
they never commit or enter writer admission. Valid protocol-floor 0 and 1 reads
need no write-protocol header.

Supported PostgreSQL 18 reads use 2-second lock, 5-second statement and 8-second
total transaction budgets. Unsupported database versions/settings fail closed.
Budget/database failures return generic `503 inventory_read_unavailable`; failed
connections are rolled back or invalidated before reuse. SQLite is only the
functional test surrogate and establishes no timeout or concurrency guarantee.

The exact inventory namespace is private and no-store, including error responses.
Uvicorn strips inventory query strings before access-log formatting and inventory
correlation IDs are server-generated. Supported edge logging has its own narrowly
scoped query-redaction verification.

`RESERVE` is negative; `RELEASE` and `CONSUME` are positive hold finalizations.
Current consumption atomically appends a negative physical-issue `ADJUST`, which
may appear on another page. Historical standalone consumption remains unchanged;
readers must not infer missing links or reconstruct availability from one page.

## Verification boundary

Tests under `services/platform/tests/inventory/` cover exact cursors, public
projection, current authorization, read-only preservation and actual Uvicorn logs.
`test_inventory_read_postgres.py` requires the guarded dedicated local
`OCWP_TEST_DATABASE_URL` and tests real lock waits, timeouts, cleanup and
`EXPLAIN (ANALYZE, BUFFERS)` on 20,001 products and 100,000 ledger rows. An absent
PostgreSQL server is an explicit skip, never a pass. Plan evidence is written to
`artifacts/inventory-read/backend-postgres-explain.json` only when that test runs.
`backend-postgres-evidence.json` is initialized incomplete for each test run and
becomes complete only after all 43 real PostgreSQL cases finish their assertions.
It records safe elapsed timings, cleanup results, source hashes and the scrubbed
plan file's digest. `OCWP_INVENTORY_READ_EVIDENCE_DIR` can isolate direct from
aggregate evidence. No index is added and no budget may be raised to hide an
unacceptable plan.

The [accepted ADR](../../../../../docs/02-technical-architecture/2026-10-15-connected-inventory-read.md)
defines the exact wire and authority contract. Offline inventory, write UI,
reconciliation, quotes and deployment remain outside this read slice.

For a dedicated fail-closed hosted run, use
`python scripts/ci/inventory_read_proof.py`. It invalidates previous evidence before
preflight, runs the 43 cases on the guarded local test database, then requires a
fresh complete artifact, the exact case set, current source hashes and matching
scrubbed-plan digest. Its bounded files are isolated under
`artifacts/inventory-read/pg-direct/`; absent PostgreSQL or skipped cases cannot
satisfy this gate.
