# ADR: serialize supported projection writers per organization

Status: first published head hosted-verified; final main30 reconciliation pending evidence.

## Context and invariant

Foundation ADR-007, OFF-001/003/005–009 and server reauthorization require
atomic domain changes and discoverable incremental continuity. Customer,
bicycle and service-order REST creates and order transitions currently bypass
`sync_changes`. PostgreSQL sequences allocate before commit, so concurrent
writers can commit cursor N+1 before N and permanently hide N behind a reader's
cursor. Sequential/SQLite tests cannot establish this concurrency property.

## Decision and bounded plan

1. Observe failing REST-to-feed tests, plus deterministic PostgreSQL tests for
   same-organization ordering, rollback, independent organizations and revocation
   while waiting (local PostgreSQL unavailable; hosted proof remains required).
2. Hold the existing organization's row lock before supported domain reads,
   mutation receipt lookup, writes and cursor allocation, until caller commit or
   rollback. Use the same lock as account administration. At HTTP write entry,
   refresh persisted actor/session/grants after the lock wait, then authorize
   the operation again. Preserve the token's effective restriction and the HTTP
   dependency's literal grant intersection: current persisted grants intersect
   the already-narrowed incoming principal. Administration's wildcard expansion
   is not adopted by operational writers.
3. Centralize projection serialization and feed/outbox append without committing;
   direct REST and sync share it. Domain rows, order events, receipts, feed and
   outbox succeed or roll back in the same transaction. Per-mutation savepoints
   remain supported; push owns the organization lock outside its savepoints.
4. Keep numeric v1 feed and REST schemas unchanged. No migration or client
   activation is introduced. Test exact projections, rollback and single append.

Organization-level serialization deliberately trades parallel write throughput
within one organization for a simple commit-order guarantee. Other organizations
remain independent; global numeric cursor gaps are valid because pulls always
filter one organization. SQLite remains a functional surrogate only. Future
writers/imports/deletes/transfers must adopt the lock and feed protocol before
being called projection-compatible. Transactions must acquire organization
before entity/actor locks; multi-organization write transactions are unsupported.

## Nonclaims and rollout

Historical REST-only data still requires an authoritative baseline; replay from
zero cannot backfill it. Inventory, quotes and full historical order timelines
are not complete offline projections. No baseline protocol, cache context or
production IndexedDB activation is delivered. All API writers must run the new
server version before ordered continuity is relied upon; old server writers are
not fenced by this change. Old browser bundles can reopen newer IndexedDB and
write legacy stores: a schema version is not a mixed-client writer fence.
Multi-user activation and physical/browser qualification remain gated.

## Evidence

- Observed REST regression before implementation: all four HTTP writes succeeded,
  but the change feed returned no rows. Fixed test validates each full projection,
  one outbox append per write, and the single order event.
- Removing the new HTTP writer refresh reproduced 20 stale-authority failures;
  restored implementation passes all five entrypoints across session revocation,
  deactivation, grant contraction and location change.
- Injected post-feed failures prove rollback for all three REST create paths and
  order transition, including domain rows/event/feed/outbox.
- Initial local Python suite: 780 passed, 70 skipped. Ten new PostgreSQL cases
  skipped because `OCWP_TEST_DATABASE_URL` is unset; no SQL concurrency red/green
  proof is claimed. They cover ordered commit/rollback, other organizations,
  refreshed grants/session/location/active state, mixed REST/sync, identical
  concurrent replay and HTTP grant revocation during a server-observed lock wait.
- Ruff check/format, mypy (77 source files), OpenAPI, generated TypeScript client,
  repository contract and diff whitespace checks passed. No public schema changed.
- Independent review found no introduced correctness/security defects, then
  reran 52 focused tests successfully with ten PostgreSQL skips. Runtime signoff
  remains conditional on hosted PostgreSQL qualification of the integrated tree.
- Source inventory found only the direct routers and `SyncService` writing the
  supported domain records; inventory reads service orders but does not mutate
  them. No inventory/quote projection completeness is implied.

The initial bounded branch started at
`675fe209fa0b038156ba0c57c44f520b2e2de376`. It was subsequently reconciled onto
actual main after PR29, `f87205157e298f5c1c7c3f08d024fe822d84582b`, preserving its
authenticated application context, identity validation and full receipt-envelope
checks. The organization lock is acquired after pure identity validation and
before receipt lookup; no domain reads precede it. `identity/router.py` remains
unchanged from main29. No production deployment or client activation ran.

### Literal authorization compatibility follow-up

A 125-case token × initial-account × post-wait-account matrix exposed 24 failures
when reusing administration's expanded wildcard grants unchanged. For example,
incoming `{customers.write}` and newly persisted `{*}` retained write permission
where HTTP literal intersection requires no grant. The incoming principal did
bound semantic authority, but that was insufficient to preserve existing policy.
`lock_writer` now keeps the audited organization/actor locking and session/scope
checks while returning current actor literal grants intersected with the incoming
principal. No administration policy changed. All 145 authority tests (125 matrix
and 20 HTTP stale-dependency cases) pass after the fix. Final broad evidence is
recorded in execution state; PostgreSQL remains pending.

Main29 reconciliation verification: full Python suite 975 passed, 75 skipped;
Ruff full check/format, mypy (77 source files), OpenAPI/generated-client and
repository contracts passed. The 75 skips include ten new ordering tests and
pre-existing PostgreSQL/environment cases; real PostgreSQL acceptance remains
pending hosted qualification. No browser execution was attempted locally.

## First published head: exact hosted proof and main30 reconciliation

Published head `b3ce95ee581e939b9dbbf8b9f15c19bfbdbde79a` passed on its first
attempt. Tested synthetic merge `6ba4646c2a8210e03a91e7c3124ce9b3803432fa`
has tree `45e4259f8a37c4ea5da1cb2e2b5c749c0b38750f`, equal to the published head.

- [CI run 38561799721](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38561799721):
  1,047 Python tests passed, three documented unrelated skips; all ten new real
  PostgreSQL ordering cases executed successfully, both directly and in the
  qualification verifier. The skips concern two database-specific migration
  variants and missing host PostgreSQL 18 backup clients; the separate runtime
  workflow passed the actual backup/restore check.
- 98 frontend core and one API-client test passed. Browser execution: 23 direct,
  ten retry-free repeats and 23 qualification reruns, 56 total passed.
- Qualification artifact `11892357812`: passed, 27/27 checks. Browser artifact
  `11892372835`. No reruns or accepted failures.
- [Runtime run 38561799869](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38561799869):
  11 checks passed including real PostgreSQL restore and browser offline
  convergence; three ARM64 image builds passed. Artifact `11892981300`.
- [Security 38561799800](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38561799800)
  and [DCO 38561799846](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38561799846)
  passed. Physical hardware qualification remains separate.

The final reconciliation is a true merge of actual main30
`840f3514b5b65ae6bf13f86d69836bd4e8cea37d` into the published PR31 ancestry,
without rewriting published history. Only the changelog, manual checklist and
execution-state additions overlapped, and both increments' records were kept.
Server product/tests remain identical to published PR31; kernel/client/workflow
files remain identical to main30. The kernel stays isolated and inactive;
production remains v4 and no authentication-context or baseline is activated.
Prior hosted proof is not asserted to verify this new combined tree: final
integrated hosted qualification remains required.

Final local combined-tree aggregate: 21 checks passed, zero failed and five
explicit environment blockers (PostgreSQL integration, Docker, PostgreSQL client,
managed-policy-blocked IndexedDB browser benchmark and browser E2E). Python:
975 passed/75 skips; frontend: 158 passed; API client: one passed. Static analysis,
contracts and production PWA build passed. An initial local dependency-link error
in the UI workspace was corrected without source changes before rerunning the
complete aggregate. Independent reconciliation review verified byte-identical
server and client boundaries above and found no defects. Final hosted CI remains
pending; historical baseline, mixed-writer rollout and physical gates stay open.
