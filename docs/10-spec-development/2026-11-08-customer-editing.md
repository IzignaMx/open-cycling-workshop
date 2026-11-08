# Existing-customer editing · 2026-11-08

Status: **locally verified memory-only unsaved-edit candidate; hosted/browser
qualification pending; unpublished**. Base main `463ac45d39812f3b4d92e5066b9e40ee6c598e67`, tree
`6b289f20f7561decdf66be49a2258dafe43a5678`.

## Latest selected scope

The user authorized name/email/phone editing as an independent prerequisite while
V0.1 remains partial, then explicitly chose **no retention of unsaved edit drafts
across sessions or interruptions**. The user clarified no versions are installed
or in production. Old-version enforcement is separate research. Follow the current
[design](../superpowers/specs/2026-11-08-customer-editing-design.md).
FR-CUS-003/R02-T001 remains partial; no broader CRUD, consent, merge, export or
deletion completion is claimed. No new publication, merge or deployment authority.

Unsent editing fields stay in memory; interruption/reload discards them with an
explicit UI warning. Successfully saved updates retain the existing durable journal
and normal sync/replay semantics. These are not unsaved drafts. Creation/order
recovery, existing 24-hour TTL and logout cleanup are unchanged. Local saved does
not mean server-confirmed; unknown acknowledgment cannot imply rollback or retry.

## Implementation

The update preserves customer identity, scope and creation time and uses the
opening base version. Current authority/version and blocked-aggregate state are
checked again atomically before append. Known conflicts refuse editing; concurrent
same-version confirmed/optimistic conflict is covered by the transaction guard.
Exact-ID replay remains a no-op. A stale callback cannot restore private fields to
a newer session or view. Dirty cancellation is explicit; duplicate clicks are
single-flight. Shared input validation rejects NUL/lone surrogates and preserves
astral text without HTML maxlength truncation.

No backend API/schema, wire contract, dependencies, workflow or local database
migration is introduced. The original checkpoint types/store/reducer, database,
CaptureRecovery/CaptureVisit and their tests are restored exactly to baseline.

## Historical rejected design, not current blockage

The first uncommitted durable-edit design extended v8 checkpoint data in-place to
v9. An archived-source/fake-IDB probe reproduced old maintenance deleting valid
new content. The opposite-direction cleanup fix did not resolve that reverse path.
A sidecar design was considered but not implemented because an old client could
not purge its private fields on logout. Neither design was published, deployed or
used with real data. The user then chose memory-only editing and clarified there
are no installed prior versions. Preserve these findings as synthetic design
history, not an incident affecting deployed users. The unsafe code is removed.

Earlier focused passes and full Python 6,069/685 skips belong to that superseded
working state, not final evidence for the selected implementation. Final checks
are recorded separately below. No full-suite pass can erase a known failing design.

## Baseline acceptance, not candidate evidence

[PR95](https://github.com/IzignaMx/open-cycling-workshop/pull/95) is merged. Its fresh
main CI 42424473619 qualified Python 6,695 plus 58 exact intentional skips,
frontend 1,299/API one and aggregate 27/27. Ten checks/four workflows passed on
attempt one. The PR95 receipt supersedes source-stage pending entries only for that
accepted source. Large browser archives were not byte/trace/screenshot reviewed.

## Validation limits

Native Chromium preflight fails before loading the app: `socket() failed:
Operation not permitted`, including the permitted escalated path. PostgreSQL and
Docker are unavailable locally. No browser flags or synthetic-database guard were
weakened. Playwright authorship/collection and fake IndexedDB tests are not native
browser execution, physical storage proof or full crash/device-loss recovery.
The affected browser and genuine PostgreSQL stages need separately authorized CI.

Physical T1–T8/R01-T035 stay deferred, not accepted. Real installation, manual
assistive technology, broader OFF-007, capacity/M2, real-data restore and deployment
remain separate. SPENT40927223929 and UNKNOWN41011497919 are unchanged. Pages and
quote activation are untouched. No production customer data was used.

## Final local evidence for the selected implementation

The final aggregate returned **partial, exit 0 with --allow-blocked**, not global
V0.1 acceptance: 21 executed checks passed, zero failed, five environment blockers.
Python 6,069 passed/685 existing environment skips/12 warnings in 379.48s;
frontend 1,355 passed with zero skips/failures; API client one passed. Repository,
HTTP runtime smoke, offline/API types, OpenAPI/generated contracts, Ruff 395 files,
mypy 126 source files, full ESLint/Prettier and current/pinned-legacy PWA builds
passed. Production and tests stayed frozen through this run; only evidence/status
text was stamped afterward and repository/format checks rerun.

The five blockers are genuine PostgreSQL integration, Docker, psql,
IndexedDB 100k native-browser proof (managed Chromium navigation restriction) and
browser E2E (dedicated synthetic PostgreSQL unavailable). The earlier direct
Chromium socket restriction also remains recorded. No restriction was bypassed.
The three isolated E2E cases collect/typecheck but have not executed locally.

An initial aggregate found an implicit ChangeEvent type under the offline compiler
and lint scanning generated independent-review copies. The explicit type annotation
was corrected; generated evidence was moved outside the checkout without changing
lint exclusions. The complete final aggregate above passed all available checks.
The initial failed receipt is retained separately, not overwritten or called green.

Independent review passed 39 focused cases and four additional probes: every unsent
field absent from all IndexedDB tables/sessionStorage, unchanged creation/order
drafts surviving reload and purging logout, actual one-operation lost-ack behavior,
no draft/autosubmit after reload, and atomic conflict/version refusal. Original
schema/checkpoint/recovery files match base 463ac45 exactly. The 132 restored capture
regressions and 16 focused edit tests are overlapping subsets, not additive totals.
No blocking source finding remains for the chosen memory-only scope.

RED evidence exists for original builder/repository/conflict behavior, memory-only
owner policy and offline event typing. An initial memory-runtime RED attempt was
invalid because setup overlapped recovery restoration; it is not counted as a
valid regression reproduction. The final actual-runtime/storage probes above are
executed GREEN evidence, distinct from that failed setup attempt.

Receipts are in the local evidence package under
`artifacts/customer-editing-volatile-20261108/`; they are not hosted CI evidence.
Local environment: Python 3.13.5, Node 24.22.1, pnpm 11.25.0. Dependency lockfiles are
unchanged. A separately authorized publication needs fresh candidate CI and review
before merge; fresh main must then qualify separately. No publication occurred.
