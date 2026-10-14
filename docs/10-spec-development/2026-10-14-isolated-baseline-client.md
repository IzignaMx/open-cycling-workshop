# Isolated bounded baseline client: implementation evidence

Base main34: `2723ec321a606a69a2516f1eaea4d96600354f8f`.
Base tree verified before implementation: `033665e81c4b547da715c8f12441a72f650ef94d`.
The remote main was freshly fetched before creating a separate worktree.

Scope and acceptance are defined by the
[ADR](../02-technical-architecture/2026-10-14-isolated-baseline-client.md).
Source remains unactivated; actual server advertisement is null. Initial
baseline ingestion is distinct from future ongoing delta/production offline
reload integration. No production App/defaultDB imports, schema migration,
legacy recovery/attribution, cutover, credentials or deployment occur.

## TDD and local evidence

Observed first failures before implementation:

- Existing active v5 flags without completion metadata incorrectly regained READY.
- An ordinary READY read accepted a null-protocol context.
- Durable start API was absent before its pre-HTTP identity test.
- New wire/transport/coordinator modules were absent before their tests.
- Retry-After of 1800 seconds was incorrectly shortened by the initial transport
  implementation; the regression failed before preserving the full safe delay.
- Additional wire/transport regression tests exercised immutable capture,
  cancellation, stream interruption and callback exception sanitization.

Focused tests use real Dexie plus fake-indexeddb, injected clocks/fetch and
controlled completion ordering. They are not native browser proof. They cover
closed DTOs, long supported Text, UTF-8/byte bounds before parse, timestamp
microseconds, exact replay, partial/contradictory-page rollback, fresh private
partitions, reload/resume, quota failure, current-session guards, same-generation
late start/activation, completion-proof reuse, null admission and failure holds.
Existing kernel fixtures provide explicitly synthetic complete proof; the actual
null server cannot activate them.

Review corrections were independently reproduced before their fixes: full retained
proof validation now rejects malformed start/context/receipt DTOs across ordinary
read/reuse/dispatch/offline boundaries; failed durable holds disable only the
matching local session; service orders use the actual `orders.read` capability;
concrete multi-segment administration grants remain literal; and original start
expiry is not incorrectly bounded by the earlier context verification timestamp.
An actual-server 35-microsecond creation-time difference reproduces the last case.

Current local checkpoint: independent review ran 225 focused access-kernel tests,
zero skips, and generated actual FastAPI responses for all five steps/all three
entity types, then consumed them unchanged through JS wire validation and Dexie
staging. Ordinary null start and activation were refused, and journal history
remained unchanged. This non-browser runtime contract proof does not replace the
hosted native journey. Final frontend core: 323 passed, zero skips. TypeScript (real and offline shim),
ESLint/Prettier, isolated build, production PWA build, repository contract and
production helper-isolation checks (2/2) pass. Real native and Dexie-wrapped quota/transaction-abort errors receive resumable
storage holds; failed hold persistence disables only the matching local session.
These additional error-shape regressions were observed failing before correction.
Local Python checkpoint: 1107 passed,
140 explicit environment-dependent skips. Aggregate checkpoint: 21 checks pass,
zero fail, five explicit environment blockers (PostgreSQL, Docker, PostgreSQL
tooling, managed browser benchmark, configured production E2E target). Final-tree
aggregate rerun is recorded separately before handoff; none of these blockers is
represented as passing evidence.

Independent review found no remaining concrete source issue after corrections.
It also verified exact request/origin/evidence preservation on reopen at all five
protocol phases, nonempty journal history and activation-pending resume beyond
the baseline deadline while actual null-protocol authority remains denied.
Near-limit regression: a valid 1,048,570-byte page and exactly 16,384-byte start
retain original validated timestamp spelling within their budgets. Only merged
projection equality normalizes timestamps; changed equivalent raw replay is
rejected. No metadata/wire bound was increased.

## Actual server/native journey

The isolated browser configuration starts actual FastAPI using a disposable,
explicit SQLite `_test` file and existing public E2E fixture identity. It exercises
historical REST-created data of all three types, more than one page, changes during
scan, lost responses after server effects, reload/resume, completion and server
activation validation. It verifies that ordinary null-protocol paths stay
unusable and journal/delivery/event values survive exactly. It is lower-level
protocol qualification, not supported-protocol production activation, PostgreSQL
locking proof, or a physical-device result.

Local native execution is blocked by the execution sandbox. Chromium launch
reported `socket() Operation not permitted`; an escalated isolated retry failed
in the sandbox wrapper before the command ran. No explicit review denial was
reported; no control was bypassed and no further browser retries were attempted.
The existing hosted Chromium workflow is the qualification route. Type/build
success does not close this gate. Exact final-head hosted evidence is pending.

## Still open

- Final-tree hosted qualification and any publication/reconciliation rechecks.
- Exact-head hosted isolated native journey and unchanged production PWA suite.
- Genuine advertised-protocol negotiation and activation, separately authorized.
- Production combined initial/delta/offline-reload integration and old-writer,
  restore/session, legacy recovery, physical-device and accessibility gates.

Do not infer installation or production rollout authority from source tests.
