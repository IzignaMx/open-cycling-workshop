# Inventory current-authority barrier and private HTTP cache policy

Status: implemented; exact-head hosted PostgreSQL evidence pending.
Base: `2723ec321a606a69a2516f1eaea4d96600354f8f` (main after PR34).

Requirements: FR-INV-001/002/003/004, FR-IAM-002/004/006/008, FR-SVC-011,
BR-006 and SEC-002/003. This is a bounded security correction to existing
commands, not a protocol, schema, credential or production-client activation.

## Source-supported defect and decision

The HTTP authentication dependency reads the account in a separate session and
returns a detached effective principal. Before this correction, inventory
product creation never refreshed it; a product INSERT could wait behind an
organization foreign-key lock. Movement creation locked the product before
checking that old principal. An administrator could revoke the session,
deactivate the account or contract grants/scope during either wait, after the
request's initial authentication but before its effects.

Both inventory write boundaries now use the existing `lock_writer` policy:
organization, then fresh persisted actor, then product where applicable. Product
creation takes the barrier before its location lookup. Movement creation takes
it at `record_movement` entry and verifies the refreshed write capability before
any product read/lock; the actual product location is still checked immediately
after the lock. Locks last until the existing caller commit/rollback. No new
transaction or independent commit is introduced.

The writer helper retains literal persisted grants intersected with the already
narrowed incoming token/account snapshot. Administration's wildcard expansion
is not reused as inventory authority. Session version, active state and scope
are rechecked. Missing/revoked sessions refuse with 401, contracted capabilities
or incompatible newly narrowed scope with 403. A still-valid command ordered
before revocation can commit; a command ordered after it must refuse.

The accepted [inventory atomicity ADR](../02-technical-architecture/2026-10-13-inventory-command-atomicity.md)
and [organization writer ADR](../02-technical-architecture/2026-10-14-ordered-change-feed.md)
continue to govern. Product locks, idempotency, actor binding, stock arithmetic,
whole-reservation finalization and atomic CONSUME plus ADJUST are unchanged.
Inventory does not become a feed projection. The coarser organization barrier
serializes inventory with other supported writers in the same organization;
independent organizations remain independent. Old server binaries are not fenced.

## Separate minimal HTTP-cache correction

The existing context/baseline no-store middleware now also covers the exact
login, me, logout-all and change-password paths, the `/api/v1/admin` segment
family, and exact `/api/v1/locations`, including trailing-slash redirects.
Successes, safe validation/auth/domain/database errors and sanitized unexpected
failures carry `Cache-Control: no-store`. Sensitive request correlation remains
server-generated; public health retains its supplied-ID behavior. Adjacent
prefixes and unrelated routes do not gain this policy.

This closes a source-visible header gap before any administration UI. It is not
evidence of an observed cache leak, cache eviction, a browser rollout or a new
authorization mechanism. No public response schema or capability changes.

## Verification and evidence boundary

- Functional stale-dependency RED: 36 failed, six passed. After the correction,
  all 42 cases pass. They exercise product creation, every movement kind and
  exact replay across session revocation, deactivation, grants, incompatible
  locations and organization-scope contraction. All denied cases preserve ledger
  rows and create no product. Literal wildcard compatibility and authorization
  before product lookup have explicit controls.
- Existing inventory, literal writer-authority and ordered-feed focused suite:
  394 passed, 31 PostgreSQL-dependent skips. These SQLite/functional checks do
  not prove lock waits. One test assertion initially used the wrong SQL table
  name (`user_accounts` versus actual `users`); correcting that fixture assertion
  did not change production behavior or the observed stale-authority failures.
- New PostgreSQL tests are authored and collected, not locally executed:
  twelve product/movement wait cases (five authority changes and rollback),
  writer-before-revocation ordering, and independent-organization progress.
  The fixture holds organization → actor → product and observes the waiting PID
  with `pg_stat_activity` plus `pg_blocking_pids` before changing authority.
  Both the vulnerable product/INSERT wait and corrected organization wait are
  valid observations; the response and zero-effect assertions decide correctness.
- Existing real-PostgreSQL stock/replay races retain their outcome assertions.
  Their contention proof now requires the actual two-edge graph: one product
  waiter blocked by the fixture and one organization waiter blocked by the first
  request. It does not substitute elapsed time for observed contention.
- HTTP cache RED: 78 failed and 13 boundary controls passed; GREEN: all 91
  passed. Tests use actual FastAPI routes with synthetic SQLite accounts.
  Unexpected 500 and database 503 cases inject failing dependencies to test
  error containment; they do not claim a naturally occurring database failure.
- The first full run found two compatibility-test failures (1,238 passed,
  154 skipped): an audit-rollback test expected an escaping exception rather
  than the newly sanitized 500, and an earlier in-process Alembic migration
  disabled the application logger before a context log assertion. The first
  now requires 500/no-store while retaining both database rollback assertions.
  Logging tests locally restore the app logger with pytest monkeypatch and
  require a generic safe log; migration/runtime logging code is unchanged.
  The explicit logging-order reproduction went from 13 failed/14 passed to
  27 passed. Existing context/baseline preservation tests passed 74 cases.
- Ruff check/format, mypy (87 source files), OpenAPI/generated-client and
  repository contracts passed. Final combined local aggregate: 21 passed, zero
  failed and five explicit environment blockers. Python: 1,240 passed and 154
  skipped; frontend core: 216 passed; API client: one passed. HTTP smoke and
  production PWA build passed. Blockers are PostgreSQL integration, Docker,
  PostgreSQL client, managed-browser IndexedDB benchmark and absent E2E database.
- Independent source/security review found no actionable defect. On production
  and test head `17b167186df72c278856b8c5aaf915e12c0b4f02`, the reviewer ran 481
  inventory/cache/context/admin cases successfully (21 PostgreSQL skips), plus
  145 writer-reauthorization cases. Ruff check/format of 17 relevant files and
  diff whitespace passed. Reviewed inventory commit:
  `dd12a0180b8aa33cfd13e4b3a4fb62524d9fefe8`. No source changes followed this
  review; final documentation reconciliation has its own format/repository check.

Local PostgreSQL/Docker is unavailable and `OCWP_TEST_DATABASE_URL` is unset.
Neither a PostgreSQL RED nor GREEN is claimed. Hosted qualification of the exact
candidate is required before acceptance, including all updated contention cases.

## Rollout and stopping boundary

No migration, deployment, installation, credential, client protocol floor,
receipt-binding change, baseline advertisement, production App/Dexie wiring or
legacy-journal recovery is included. Snapshot advertisement remains null and
the production v4 client remains unchanged. Existing physical Windows/Android,
accessibility, backup/restore and multi-user activation gates stay open.

For an authorized future server update, use the existing reviewed upgrade and
backup/restore process and drain old writers. This source fix does not supply a
mixed-version fence. Do not clear browser data or alter historical inventory
entries to adopt the correction.
