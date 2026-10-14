# Effective identity and sync authority prerequisite

Status: implemented locally; exact-head hosted PostgreSQL/browser qualification
and independent review are pending. This bounded security increment does not
enable end-user permission administration or qualify a release.

## Scope and traceability

Base: `59ad7e96ee1f32308a63ffa9248b528685a5221c` (merged administration PR #27).
This increment contributes to FR-IAM-002, FR-IAM-004, SEC-002,
Foundation ADR-007/ADR-013, Security/Privacy §§8–10 and §18, and the Master
Loop's sync idempotency and server-enforced authorization invariants. It follows
the [administration authorization decision](../02-technical-architecture/2026-10-14-access-administration.md)
and [change-feed authorization decision](../02-technical-architecture/2026-10-14-sync-read-authorization.md).
It hardens their existing authority boundaries without changing architecture.

## Acceptance and implemented behavior

### Current authenticated authority

`GET /api/v1/auth/me` retains exactly its existing response fields. Its
capabilities and location describe the authenticated session's effective
authority, rather than raw account grants. Both the request dependency and the
response revalidation use the same literal intersection of persisted and token
capabilities. This deliberately preserves existing wildcard semantics: `*`
intersected with only explicit grants does not newly confer those grants. No
catalog expansion or grant widening is introduced.

The response transaction locks the organization, then reloads/locks the account
with `populate_existing`, matching the administration organization-before-user
order. It rechecks active state, user/organization identity, session version,
location compatibility and current grants after any lock wait. Removed,
disabled, revoked or incompatible-scope accounts return 401. A newly wider
account does not widen the already authenticated principal; a narrower account
narrows the response. Display name is loaded with that account snapshot.

This is a current connected read, not an authorization-epoch or snapshot API.
It does not expose an account revision, freeze future authorization changes,
or make browser-supplied identity metadata trustworthy.

### Server-attributed sync transitions

The sync HTTP router passes the authenticated principal's user ID in the
server-only typed `SyncApplicationContext`. New service-order transition events
use that actor. Legacy `transition.actor_id` payload members remain accepted
but have no attribution authority, including forged, absent or non-string
values. The action, state/version rules, note and domain transition behavior
remain unchanged.

Direct `SyncService.apply` callers creating a new order transition must pass an
explicit trusted context. Missing context conflicts before any event or
transition is written; there is no payload fallback. Customer/bicycle/order
creation callers and the standalone `ServiceOrder.transition` domain API retain
their existing interfaces. Existing service tests now supply explicit context
where they previously implicitly trusted the envelope actor.

The actor is the authenticated submitter at application time. This does not prove
who originally authored an offline mutation, add a receipt actor binding, or
rewrite historical timeline events. Browser user-switch/pending-write
reconciliation remains a separate rollout prerequisite.

### Stored receipt tuple binding

Before acknowledging an existing mutation receipt, compare every stored
envelope identity field with the submitted envelope: organization, location,
entity type, entity ID and operation. Any mismatch produces the existing
per-mutation `sync_conflict`, without a new business effect, timeline event,
receipt, feed row or outbox event. Independent valid batch items still commit.
The API's current grant and scope checks still precede receipt lookup.

A matching tuple returns the original applied result exactly once. Receipt
storage has no actor, payload digest, base version or original request timestamp.
The implementation cannot compare or attest those values and does not invent
them. A same-tuple replay with changed payload/base version acknowledges the old
result and does not apply the changed data. Original-actor/payload binding,
legacy-null migration and stronger concurrent-replay semantics require their
own design and evidence.

## Regression evidence

- Initial HTTP/current-user regressions: **15 failed, 7 passed** before the
  implementation, reproducing effective-grant/location overstatement, stale
  session/scope acceptance, forged actor attribution and four receipt tuple
  mismatches. Passing controls covered existing compatible behavior.
- Additional direct-service regressions: **5 failed, 2 passed** before the
  implementation. All four previously unchecked tuple fields and missing
  trusted actor context failed. Existing cross-organization rejection and
  same-tuple payload/base-version compatibility already passed.
- Focused final unit/API suite: **43 passed**. This includes three unchanged
  authorization controls showing replay is denied after a grant, location or
  session change, plus preservation of standalone transition/domain semantics.
- Five real PostgreSQL tests use the existing dedicated-target, isolated-schema
  administration fixture and observable `pg_stat_activity` lock waits. They
  cover session revocation, deactivation, incompatible location, grant removal
  and grant expansion while `/me` waits. Their runtime result remains pending
  until a configured PostgreSQL run; SQLite is not row-lock evidence.
- Full Python suite: **787 passed, 65 skipped**. The skips are PostgreSQL-specific
  tests without a configured dedicated `OCWP_TEST_DATABASE_URL`, including the
  five new contention cases; they are not established by SQLite tests.
- Aggregate local qualification: **21 checks passed, zero failures, five
  environment blockers**. This includes 74 frontend core tests, one API-client
  test, real HTTP smoke, Ruff lint/format, mypy (75 source files), ESLint/Prettier,
  TypeScript checks, unchanged OpenAPI/generated TypeScript contracts and the
  production PWA build. The ordinary frontend `tsc --noEmit` also passed directly.
  Existing installed toolchains were reused; this does not claim a new frozen
  install. A baseline attempt found an omitted local `packages/ui` dependency
  link; fixing that test-tool setup required no source/lockfile/config change.
- The five aggregate blockers remain PostgreSQL integration, Docker, psql,
  managed-browser navigation for the IndexedDB benchmark, and browser E2E setup
  without its dedicated database. No browser-policy bypass was attempted.
- Independent review and exact-head hosted CI/Security/DCO results are pending;
  local build evidence does not substitute for PostgreSQL or browser execution.

## Compatibility, operations and limits

No database schema/migration, public request/response schema, generated API
contract, client-cache implementation, credential change, real-account action
or deployment is introduced. Existing receipts and history are retained.
Development version identifiers stay unchanged; the changelog records this
unreleased correction. No new operator setup is required.

The [administration rollout gate](../02-technical-architecture/2026-10-14-access-administration.md#explicit-product-and-rollout-boundaries)
still requires safe per-user cache isolation, authorization epoch, scoped
resnapshot/backfill and pending-mutation reconciliation. Numeric pull cursors,
already downloaded offline data and the offline revocation window are unchanged.
Physical Windows/Android, manual accessibility, broader security, recovery and
other release gates remain open wherever their own evidence is absent.
