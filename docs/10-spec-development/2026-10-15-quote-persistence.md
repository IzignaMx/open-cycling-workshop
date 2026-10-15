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
