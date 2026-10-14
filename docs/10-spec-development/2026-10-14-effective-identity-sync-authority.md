# Effective identity and sync authority prerequisite

Status: the bounded server checkpoint is independently reviewed and hosted
verified. Reconciliation with merged structural themes requires its own
exact-head hosted qualification. This increment does not enable end-user
permission administration or qualify a release.

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

The service first rejects blank identity fields or any whitespace in mutation,
organization, location or entity IDs. Bicycle/order constructors previously
normalized such strings, so accepting a noncanonical envelope could store an
applied identity different from the submitted identity and break an identical
retry. Rejection happens before lookup or effects and remains a per-mutation
conflict. IDs are not silently normalized or equated; this is not a new global
UUID/version validator and does not change standalone domain constructors.

Preexisting malformed receipts/history are retained exactly as stored. A
malformed replay now conflicts without acknowledging or rewriting it. Do not
automatically substitute a normalized ID, delete the receipt, mint a replacement
mutation or rewrite history to bypass that conflict. Any affected pending client
operation needs explicit history-preserving reconciliation; this increment does
not implement an automatic recovery workflow or claim malformed legacy inputs
are safely replayable. Valid historical same-tuple retries remain compatible.

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
- Focused final unit/API suite: **81 passed**. This includes three unchanged
  authorization controls showing replay is denied after a grant, location or
  session change, plus preservation of standalone transition/domain semantics.
- Independent review reproduced an accepted-input edge: an order ID padded to
  the wire's 36-character length applied with a normalized ID, then an identical
  retry conflicted. Before the corrective guard, **37 additional regressions
  failed**; all 37 pass after it. They cover exact HTTP retry/batch isolation for
  trailing-space/internal-tab/nonbreaking-space identities, each service-level
  identity field and unchanged malformed legacy receipts. A further durable
  test preserves every stored order/event/feed/receipt/outbox column on a
  different authorized user's same-tuple changed-payload replay.
- Five real PostgreSQL tests use the existing dedicated-target, isolated-schema
  administration fixture and observable `pg_stat_activity` lock waits. They
  cover session revocation, deactivation, incompatible location, grant removal
  and grant expansion while `/me` waits. They were initially skipped locally and
  subsequently passed on hosted PostgreSQL 18.4 at the checkpoint below;
  SQLite is not row-lock evidence.
- Full Python suite: **825 passed, 65 skipped**. The skips are PostgreSQL-specific
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
- Independent review confirmed the normalization correction with its own
  37-failure pre-guard reproduction, 81-passing focused suite and full suite of
  825 passed/65 PostgreSQL skips; no further
  implementation defects were found. Review also checked current-user freshness,
  actor attribution, strict tuple authorization and historical replay boundaries.
- The local evidence above is historical and distinct from the subsequent
  hosted checkpoint and combined-main reconciliation below.

## Hosted server checkpoint and main reconciliation

[PR #29](https://github.com/IzignaMx/open-cycling-workshop/pull/29) head
`53f2758fa4ffbeaf69ef57a2d9c4e6387c906799` and its tested synthetic merge
`db7e451004e9683b2bc5ed5a5711562e197ca158` both have Git tree
`22be9cf04f5a37090f2ae09a543e355ad276e18b`, verified directly through Git commit
metadata. The merge parents are main
`59ad7e96ee1f32308a63ffa9248b528685a5221c` and that PR head.

- [CI 38557162076](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38557162076)
  passed all 27 aggregate checks with zero blockers. Downloaded qualification
  artifact `11890711098` records the exact tested merge and Python 3.13.16.
- The full Python suite passed 887 tests, including all five new PostgreSQL 18.4
  lock-wait cases. Three unrelated skips remain explicit: the host backup drill
  lacks matching major-18 clients, SQLite cannot test TRUNCATE, and PostgreSQL
  cannot test SQLite's INSERT OR REPLACE. The separate container runtime below
  proves its own real major-18 backup/restore path.
- The 74 frontend core tests and one API-client test passed. Browser execution
  passed 10 direct journeys, 10 retry-free repetitions of the two sync-chaos
  journeys, and another 10-journey aggregate run. The 100k IndexedDB benchmark
  passed (40,553.8 ms write, 166 ms count/sample), without claiming physical-device
  qualification.
- [Local runtime 38557162143](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38557162143)
  passed all 11 real-stack checks, including PostgreSQL backup/restore, restart
  persistence, actual-edge PWA offline/reconnect convergence and credential-free
  logs. Downloaded artifact `11890438957` records the same tested merge. All three
  ARM64 image builds passed; physical hardware was not tested.
- [Security 38557162059](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38557162059)
  and [DCO 38557162116](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38557162116)
  passed.

The subsequent reconciliation is a true merge with actual main
`675fe209fa0b038156ba0c57c44f520b2e2de376` (structural themes PR #28), retaining
both histories. It preserves the already reviewed server implementation and
tests byte-for-byte and the merged main frontend/workflow files byte-for-byte.
Only this security evidence is updated beyond the conflict-free merge. No new
migration, API/generated-contract change, production cache activation or real
account/deployment action is introduced by reconciliation. The mainline remains
on Alembic `0008`; future quote persistence follows as `0009`.

The combined local aggregate passed all 21 runnable checks with zero failures
and the same five environment blockers: 825 Python passed/65 PostgreSQL-specific
skips, 98 frontend core tests, one API-client test, static/contract checks and
production PWA build. No additional implementation/test edits were required.
Independent reconciliation review passed 81 focused server tests, all 98
frontend core tests, unchanged OpenAPI/generated TypeScript contracts, evidence
formatting and diff checks. It verified both parent SHAs and the byte-identical
server/frontend boundaries above; the final follow-up changes only these two
evidence documents. Fresh exact-head hosted CI/runtime/security/DCO remain pending
before integration. The earlier green server checkpoint does not qualify this
combined head. Existing manual and administration-rollout gates remain unchanged.

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
