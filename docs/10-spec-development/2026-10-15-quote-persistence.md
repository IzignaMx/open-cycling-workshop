# Quote persistence · repository-first evidence

## Architecture acceptance

The coordinator accepted the independently reviewed
[quote persistence/application ADR](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md)
on 2026-10-15 for **repository-first Increment 2 Task 6 only**. The inspected pure
quote source was `9d8dcd5f80d036f0fb7a0407584bb761dad83e95`; merged main
`d9381808c61b4682844666eb62967ccbf9afc5b9` has the identical tree
`ac1e5985e7bb89a274755e9ab0bcb2d1ec35778a` and is the implementation base.

- Final reviewed proposal SHA-256:
  `01f27bd760033cda7c9fa92f1420d7c9ba8b5a123be736bc9d2826761023b250`.
- Independent architecture review report SHA-256:
  `2be3327b843e3be9e7471fc0c4662b9c8d8de4364a36fa0e0ff20fcfc4461758`.
- All eight findings closed: complete effect associations, no mixed old server
  writers at enrollment, exact monotone authority narrowing, compact bounded
  current-order response, per-dimension candidate limits, explicit first-owner
  establishment rather than bootstrap widening, admission/proof separation and
  text-storage/catalog precision. Pure decision mode `initial` is not itself
  an order-transition instruction.
- Formatting, all five original local document links and whitespace checks
  passed on the reviewed proposal. Acceptance adds status/reference metadata;
  it does not qualify the future implementation.

## Implementation and qualification status

The first schema slice implements six registered tables: quote lineages,
revisions, typed lines, reference edges, decisions and terminal operations.
Migration `0012` is additive after `0011`; it preserves previous rows and grants,
uses scoped foreign keys and deferred root/head references, and guards immutable
history against update, delete, truncate and SQLite replacement. Only the lineage
head/version/sequence cursor is mutable. Reserved order-effect columns are not an
activation mechanism.

Observed test-first evidence: two missing-table failures before implementation;
a currency-NUL regression failed then passed; thirteen affected operator tests
failed until the existing cutover schema allowlist narrowly accepted `0012`.
Empty, old, unknown and multiple stamps still fail. No operator action ran.

- Schema tests: 84 passed, 84 skipped (83 unavailable PostgreSQL cases and one
  PostgreSQL-only TRUNCATE case on SQLite).
- Affected migration/cutover tests: 93 passed, 50 PostgreSQL skips.
- Independent schema review: no blocking finding; 159 passed, 107 explicit skips
  across its broader selected scope. Independent probes also confirmed UNIQUE
  and CHECK parity; those assertions are now retained in the schema suite.
- Frozen migration/ORM parity, scoped Ruff, mypy for four touched source files and
  whitespace checks passed. Generated PostgreSQL DDL is not live execution.

### Bounded codecs and semantic commands

Private storage codecs and immutable create/revise/decision commands now retain
one canonical semantic proof per operation. Exact integers reject booleans,
floats and coercions; bounded values remain integer minor units. UUIDv7, UTC,
Unicode, line/edge, record and complete-history limits are enforced without
changing the unbounded pure arithmetic contract. Set-valued selections normalize;
presentation order and literal evidence remain significant. Admission tokens,
incarnation and execution time do not become semantic retry fields.

- Initial missing-module REDs preceded implementation; 68 focused cases now pass.
- Independent review exposed cyclic/deep malformed input reaching an unbounded
  serializer. Preserved create/revise and forged-dataclass recursion REDs now
  return controlled `ValueError`; NUL/invalid-UTF8 JSON keys are rejected too.
- Independent closure: 311 committed tests passed (68 new plus the unchanged 243
  domain cases), and 347 additional adversarial boundary cases passed. Focused
  Ruff/format/mypy passed. These are separate counts, not one combined suite.
- JSON duplicate-key/number-lexeme/streaming admission belongs to the future HTTP
  adapter; these codecs accept already-typed private objects, not raw requests.

### Atomic repository and complete reconstruction

Repository operations require the existing transaction-owned writer admission,
then lock order and lineage. They preserve caller-owned commit, compare current
order/head/version/decision-sequence for new work, and return original immutable
receipts plus current projections for exact retries. Receipt lookup is scoped to
organization/location/order before loading proof. A generic identity/scope
conflict handles foreign uniqueness collisions without disclosing their proof.

Reconstruction joins all six tables, derives supersession from successor rows,
replays the contiguous finite operation history, and checks persisted arithmetic,
evidence, actors/times, cursors and outbox content. The only delivery fields it
ignores are attempts/published time. Quote outbox events contain scoped IDs,
kind, minimal totals/selection and distinct decision/domain versus delivery IDs;
private customer evidence, note, source and reason are excluded.

- Initial missing-repository RED preceded implementation. A real SQLite legacy
  savepoint regression showed premature commit; explicit outer BEGIN now keeps
  caller rollback authoritative. Four boolean receipt-number REDs are retained.
- Independent review found final read-expiry, omitted outbox contract facts and
  cross-scope receipt lookup gaps. Five committed regression cases failed before
  the corrections and now pass. Current repository/reconstruction tests: 82
  passed, 82 explicit PostgreSQL skips; independent exact-source review has
  closed all five codec/repository findings.
- The first broad Python run was **not a qualification pass**: 1 failed, 2,551
  passed, 407 skipped. Its failed documentation contract still assumed quote
  migration was always future. State now identifies implemented `0012`; the
  quoted-string/octal regression instead verifies that actual frozen migration.
  This run also predates the latest review fixes. A final rerun is required.
- Twenty-one real PostgreSQL race/admission/rollback cases and one dump/restore
  case are implemented, all skipped locally. The existing PG18 recovery wrapper
  additionally runs that file with its guarded disposable fixture and matching
  clients; existing branding artifact checks are unchanged.

No new order state, event, change-feed row or stock movement is written. Reserved
non-null order-effect tuples fail closed in this repository version; their
consumer and the narrow `append_change` return-value change belong to separately
reviewed stage 3. Domain mode `initial`, including later-revision decisions, is
stored as evidence and never implicitly executes the initial-transition planner.

### Final local qualification and independent review

The reviewed behavior source is `535c477b8cba8a4e552160d3908d96b28d6a8f36`, tree
`771d5b68e332afd69610dfbdd38fd4dcec5a7669`. Final documentation records its results
without changing that source.

- Full available aggregate: **21 passed, 0 failed, 5 environment blockers**.
- Python: **2,557 passed, 412 skipped**, three dependency/SQLite warnings.
- Frontend core: **773 passed**, zero failed/skipped; API-client core: one passed.
- Ruff/format, mypy for 106 source files, ESLint/Prettier, offline/API types,
  repository/OpenAPI/generated-client contracts, SQLite HTTP runtime smoke and
  current/reproducible pinned-old PWA builds passed.
- Runtime: locked Python 3.13.5 and Node 22.16.0. Installed dependencies were reused
  read-only with package links bound to this checkout. Two earlier aggregate
  attempts each had 20 passes, two build/browser failures and four blockers:
  first missing local UI React/type links, then missing local branding/UI workspace
  links. Their artifacts are retained. Completing those links changed no lock,
  dependency or source; a full final rerun, not a stitched summary, produced the
  21/0/5 result above.
- Blockers: no PostgreSQL test URL, Docker or psql; managed Chromium navigation
  policy prevents IndexedDB-100k; no destructive browser-E2E database URL.
- Independent schema report SHA-256:
  `b176203df892d54e4e5484b42be10f2ec5f894ad44c2e290d70475493fd3836b`;
  no blocking finding, 159 passed/107 explicit skips in its selected scope.
- Independent final source report SHA-256:
  `cc3950a463e9a1c9b371e16d768d5c291ae3f2de059044540d3779bd69d92a9c`;
  no remaining blocker, **786 passed/148 explicit PostgreSQL skips**. This is
  243 unchanged domain + 68 codec + 82 repository + one migration-contract + 392
  reviewer checks; it is a separate suite, not additional aggregate coverage.

Real PostgreSQL 18 migration, contention, deferred-constraint behavior, restore,
maximum-fixture runtime and exact integrated hosted/security/DCO qualification
remain open. Neither source review nor SQLite substitutes for those gates. Existing 243 quote tests, including the
unchanged original 106, remain exact-source regression requirements.

Reinspected base SQL head is `0011`; the candidate adds quote revision `0012`.
Authenticated local schema stays 7. This executor currently has no configured
PostgreSQL test URL or psql/postgres/docker binaries. Real migration, race and
restore qualification must run in the existing authorized hosted PostgreSQL
fixture; local skip counts cannot replace that evidence. No cloud database,
account, credential or persistent test service is to be created for this work.

## Scope retained

Only models/migration, strict bounded complete reconstruction, atomic repository
operations and their tests are authorized now. No route, capability catalog,
grant/adoption, synchronization, offline store, UI or operational enrollment is
activated. The accepted ADR's future application, all-ingress guard, mixed-server
writer and line-coverage gates remain open. The full durable Task 5, Task 8 and
quote/inventory journey are not complete.

## First hosted candidate and runtime diagnostics

PR44 published head `d90636d1e222b045011e041e631f317c229828e1` has the
reviewed final tree `cf6d4350d066b84fb61b8ce40255d354dd125d3a`.
The hosted synthetic merge `4520ff9e6297548a593ffa6ce9ec43c2b6d99a42`
has the same tree. These first-attempt failures remain evidence, not qualified
results or permission to rerun until green:

- [Runtime 38704714032](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38704714032)
  failed with the unchanged 180-second readiness error after `compose stop api`,
  the expected outage/502 assertions and `compose start api`. Fresh-volume
  migration/readiness, restricted DB role, bootstrap/login/customer creation,
  PWA delivery and two-browser offline/reconnect convergence had passed: seven
  substantive checks in total. The first backup had not begun; restore and later
  persistence checks were not reached.
- Runtime artifact `11958790296`, SHA-256
  `2673b7d1d24c7250e054724d5d1c15bd745f291dab4b7e2d178c2f62382cfb41`,
  contains only the existing evidence JSON. It has no container state, logs,
  traceback or readiness HTTP details. The restart's underlying cause is
  **unknown**; initial migration failure and transience are not established.
- Security run `38704714022`, all three ARM64 builds and the native ARM64 gate
  passed. These are separate scopes, not AMD64 runtime or physical Raspberry
  qualification. Independent evidence review SHA-256:
  `507d3c1ea15cc023172de462a348b9995324b145fb0a6eebc6064e9513a3a5ce`.
- [CI run 38704713983](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38704713983)
  finished failed. Direct and aggregate Python each retained **two failures,
  2,944 passes, 23 skips and three warnings**. Both failures are PostgreSQL
  negative tests for 501-character description/reason fields: the database
  correctly refuses `VARCHAR(500)` with `DataError` wrapping
  `StringDataRightTruncation`, while the tests expected `IntegrityError`.
  This is distinct from the unknown runtime restart failure.
- Recovery execution was skipped after direct Python failed, and mandatory
  proof upload therefore failed. Actual quote dump/restore was also explicitly
  skipped within both Python suites because matching major-18 clients were
  unavailable on that PATH. The recovery wrapper that provides those clients
  never ran. No restore pass is inferred.
- Aggregate artifact `11959145055`, SHA-256
  `77e2628f566a8598caddcf08232917f99a780734d378ca8fd599cf043a34f72b`,
  records **24 passing controls, two failures and one blocker**. Browser and
  IndexedDB execution lacked Chromium after its direct installation step was
  skipped. Browser artifact `11958975259`, SHA-256
  `acab74db0e1ace569e31aa166a57a1e01b80a5faf04dc5bf6567bbe012801fa1`,
  has 53 retained trace payloads explicitly reporting the missing
  `chromium_headless_shell-1234` executable, each duplicated in the report
  directory (106 matching artifact entries, not 106 distinct executions).
  Automatic workflow/browser retries
  are retained as failures, not used to claim qualified browser journeys.

The diagnostic-only follow-up touches the existing disposable runner, not the
quote domain, migration or application behavior. On failure it preserves the
first error and collects read-only state and logs for that already-generated
Compose project **before** browser, probe and volume cleanup. It admits only
fixed service/state/health/exit-code fields, never `inspect` configuration or
environment/command fields. Five service log tails are capped at 40 lines;
each probe has a five-second/16-KiB capture limit. Partial timeout/overflow
output is discarded rather than truncating a secret across a boundary. Complete
output is redacted with the generated-secret list and existing JWT detector;
failed probes cannot replace the first error. Each direct child is reaped and
its owned process group terminated on success, timeout or overflow. The readiness deadline, polling, substantive assertions and
fixture cleanup are unchanged.

TDD observed five failures for the absent diagnostic behavior before code. The
focused runtime/branding/Compose suite then passed 33 tests; Ruff/format and
mypy for the touched runner passed. This executor has no Docker, so actual
failure-path capture, the underlying restart correction and all exact hosted
runtime/restore gates remain pending. Independent diagnostic review passed 45
tests plus ten repeated descendant regressions, Ruff/format and mypy; it found
no remaining diagnostic blocker. This is separate from the pending combined
fixture review and hosted runtime evidence.
Its first review reproduced a normally exiting CLI leaving a same-group child
with detached stdio running. That failure was retained in an additional RED
regression before changing cleanup to terminate the owned group on normal exits
too; the direct child's successful return code remains intact.

## Narrow PostgreSQL refusal-test correction

The terminal hosted failures above are the real RED evidence; no local PostgreSQL
execution is claimed. The test-only correction accepts `DataError` only for the
exact PostgreSQL 501-character description/reason inputs, then requires the
original exception's exact `StringDataRightTruncation` type and SQLSTATE `22001`.
All other PostgreSQL constraint cases still require `IntegrityError`. Every
SQLite case additionally requires the native SQLite integrity-error type.
Each rejected transaction must leave exact rows in **all six quote tables**
unchanged. A missing refusal, wrong PostgreSQL error class/state, lost row or
partial write therefore still fails. Production migration, model and repository
sources and their 500-character limits are unchanged.

The two affected parameterized groups pass locally: **24 SQLite passes and 24
explicit PostgreSQL skips**. These checks do not qualify PostgreSQL behavior.
The combined quote/runtime/branding/Compose/repository suite passes **535 tests
with 188 explicit skips and one dependency warning**; the skip reasons remain
retained rather than counted as database qualification.
The combined source checkpoint `989e128d9496c2bd36350b01f576bd9e97077429`
has independent review with no remaining blocker: the reviewer reproduced
535 passes/188 skips and separately passed 42 adversarial probes (30 strict
exception/retention cases and 12 diagnostic cases). Those scopes are not added
together as aggregate coverage. Fresh exact-tree hosted evidence is still
required; original failures remain retained.
Combined review report SHA-256:
`eb21e3a6186f02f0f6a0ddcf834afab9adbac69ca2726213182d50955f486719`.

## Bounded repeated restart qualification

Follow-up head `26b589be9600163e0ee2ee978ef66ee99dfc4e05`, tree
`8feed94bdb31cd204e0b503222989babb60961d2`, passed runtime `38708608800`,
Security `38708608818`, all three ARM64 builds and native ARM64 qualification on
their first attempts. The checked-out merge `e4677109` has the same tree.
Independent hosted review SHA-256:
`8d222f3742b0fc017391e2f9072b94a024e95ae61f41e4b732f982444d57800e`.
Runtime artifact `11959013393` SHA-256:
`ae3c5f142d25a233f91a1f13b0e3e0fe85fb9f33bbe84339aa59b63b55273963`.
It records all eleven checks, one intentional API restart, generic PostgreSQL
backup/restore, authenticated recovery, down/up persistence and exact branding
bytes/metadata. Quote-populated restore and full CI are separate gates.

That successful restart does not establish a root-cause fix or explain the
original failure. Failure diagnostics were not exercised by the successful run.
The coordinator therefore accepted a bounded three-cycle qualification proposal
after independent review, SHA-256
`51f9b098d6fe5df7bacf4d2c368e73c64a87cd2ae465b0b02c2204181521ab68`.

The existing runner now requires exactly three consecutive cycles on its same
generated project: stop API, expect 502 without SPA fallback, retain static 200,
start API, wait for readiness, verify authenticated branding persistence. The
first error stops all later cycles and backup, preserves the original exception,
and reaches the existing bounded diagnostics before cleanup. Outer evidence owns
the at-most-three records before execution; each records fixed phase/status and
its cycle number. Optional elapsed seconds must be finite/nonnegative; failed
timing collection cannot replace the qualification error. Successful cycles
remain one substantive check, retaining the eleven-check total.

Readiness remains 180 seconds with two-second polls and five-second HTTP request
timeouts. Existing Compose command/workflow deadlines are separate and unchanged.
Production startup, migrations, health ordering and routing are unchanged. The
existing branding verifier compares against its initial baseline, not against
the immediately previous cycle's start time. Three passes provide bounded
resilience evidence, not a guarantee against rare failures or retroactive cause.

TDD retained 23 initial failures before the helper existed, then four timing
failure/invalid-duration regressions before hardening that diagnostic bookkeeping.
Independent review additionally reproduced an unavailable initial timing read
preventing the first mandatory stop and leaving inaccurate running evidence.
Two more RED regressions preceded making that initial measurement optional too;
qualification now continues without duration fields when timing is unavailable.
The original branding source-order assertion failed after callback integration
and was updated to assert that exact integration, without dropping its ordering
contract. An initial follow-up command referenced a nonexistent test path and
ran no tests; the corrected scope was rerun fully. Final local quote/runtime/
branding-volume/Compose/repository selection: **578 passed, 188 explicit
PostgreSQL skips and one dependency warning**. Configured Ruff/format (245 files),
mypy (106 production sources plus the runner) and repository contracts passed.
Independent source review and new exact-head hosted three-cycle/full-CI evidence
remain pending; no Docker or PostgreSQL execution is claimed locally.
