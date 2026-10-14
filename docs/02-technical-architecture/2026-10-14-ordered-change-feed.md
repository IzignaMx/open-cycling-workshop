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

## Combined-head browser failure and bounded fixture correction

Published combined head `5177d4fc2f5d2c44f2f6f638b234b8ba6120bf49` ran CI
`38564469464` (job `115853504193`). Python passed 1,047 tests with three unrelated
skips; all ten ordering cases executed. The isolated kernel browser suite passed
8 tests and frontend core passed 158. Runtime `38564469777`, Security
`38564470129` and DCO `38564469775` passed, including three ARM64 builds.

The direct PWA suite passed 22 tests and failed the order lifecycle case:
`order-lifecycle.spec.ts:115` observed a non-OK remote transition response. Its
original HTTP status and body are **unknown**. The retry separately failed a
strict locator because two records shared the fixed problem text. The later
qualification PWA suite passed all 23 tests but does not erase the direct failure.
The successful qualification invocation overwrote the earlier screenshot, trace
and error context: downloaded artifact `11894741424` contains none of those
failure files. This diagnostic loss is recorded rather than inventing a 404 or
409 explanation.

A source-level fixture defect is independently identifiable: the previous sync
label was treated as proof that a newly created intake had committed and its
acknowledgement had drained the durable queue. A bounded test-only correction
uses unique customer/order fixtures, scopes each action and conflict to that
order, requires its matching applied create response and durable queue drain,
and verifies the authoritative server state is INTAKE/version 1 before going
offline. Remote transition and timeline assertions retain exact success and
exactly-two-events requirements, with explicit HTTP status/body diagnostics.

A new controlled browser regression holds local completion, then server create,
then the real committed create acknowledgement. It is designed to demonstrate
that the old synced-label predicate can pass too early and the new readiness
barrier rejects all incomplete stages. Its controlled 404 is distinct from the
unknown original failure status. Native execution of that regression is pending
hosted proof; no local browser navigation was attempted or claimed.

Direct, retry-free-repeat and qualification browser phases now retain separate
result/report directories and always-upload artifacts. Two deterministic
artifact-routing regressions were observed failing before that change and
passing after it. The existing retry-free gate retains the two chaos journeys
and adds both order cases, five executions each (20 total), with zero retries.
No production/domain/sync/kernel implementation changed, no timeout increased,
and no assertion or acceptance criterion was weakened.

Local correction verification: aggregate 21 checks passed, zero failed, five
unchanged environment blockers; Python 977 passed/75 skipped, frontend 158 passed,
API client one passed. Strict order-fixture TypeScript check, ESLint, formatting,
contracts and PWA build passed. Playwright discovery found exactly 20 selected
retry-free repeat executions, including both new/order cases. Independent review
found no actionable defects. The controlled native-browser regression and final
corrected-head hosted acceptance remain pending; no successful local browser
execution or original failure HTTP status is inferred from these checks.
