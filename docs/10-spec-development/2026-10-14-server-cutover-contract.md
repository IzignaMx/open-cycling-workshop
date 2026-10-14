# Increment B · bounded server cutover contract

Date: 2026-10-14. Status: implemented, independently reviewed backend;
exact integrated-head hosted PostgreSQL/native qualification pending.

## Source and scope

Started on actual main35 `68933a7c61c9ed13a5f5634f3f9c3df69154f22d`, tree
`957fb12edf0c3f0afcb93e89fc748ce68a4544c2`. Reconciled actual main36
`714342c60f4163c7b4c1ebec8433995dccbeea01`, whose isolated baseline-client
product tree is `fbf5e5678188a97b8b9709e6f91cb6b250e20c9f`.

The accepted [ADR](../02-technical-architecture/2026-10-14-server-cutover-contract.md)
preceded implementation. Four reviewed amendments are implemented inside B:
signed restore-resistant incarnation, explicit context provenance, stored-proof
replay independent of incoming protocol, and forward-only migration refusal.
Foundation ADR-003/007/013, FR-IAM-002/004/006/008, OFF-003/005/007/009/012 and
SEC-002/003 remain governing requirements. No licensing or release-version change.

- Migration0010 follows0009. Only new organization/proof metadata is initialized;
  historical business/account/receipt/audit/feed/outbox values are preserved.
  The unimplemented quote reservation moves to quoted `0011`, without a placeholder.
- Every catalogued writer uses explicit transaction-owned floor admission and
  retains organization → actor → product/target ordering. Operational authority
  stays the literal captured effective-grant intersection after both waits.
- New signed `di` is checked on every authenticated route and after write/context
  locks. Login locks current org/account consistently. Expiry is rechecked after
  waits and immediately before write commit. Missing legacy `di` is floor0-only;
  present malformed/mismatched values always fail.
- Exact write headers admit only known0/1; strict sync additionally validates one
  current epoch and one selected workshop outside item savepoints. Disabled
  composition rejects strict writes. Null/floor0 remains ordinary client refusal.
- Bound receipts require original actor and complete raw canonical command even
  on an admitted protocol0 request. Legacy and corrupt proof holds have bounded
  typed error codes. See the [fixed canonical vectors](2026-10-14-command-receipt-proof.md).
- Operator status/activate/recover requires exact schema0010 and an explicit
  configured database. Activation is monotone/idempotent with honest audit;
  recovery requires active floor1 and exact expected incarnation. Rollback of
  either operation preserves state/audit; no counters or credentials are rotated.
- Closed live and retained isolated client contexts require policy2 and explicit
  incarnation. A separate genuinely enabled floor1 browser fixture exercises the
  ordinary adapter/coordinator; original floor0/null journey remains intact.
  See [client reconciliation evidence](2026-10-14-cutover-context-adapter.md).

Production App and repositories remain v4. C owns production cutover, journal
incarnation and recovery holds, applied overlays, ongoing deltas, offline reload
and exact old-bundle/service-worker queue-preservation journeys. No real target,
credential, account, activation, restore or deployment operation was performed.

## Observed regressions and review fixes

- Observed initial auth failure: signed login lacked `di`.
- Receipt tests observed both protocol0 bypass of a bound actor and protocol1
  acknowledgement of an unverified legacy receipt before implementation.
- Migration/first-owner/bootstrap/operator tests observed required red→green
  behavior before their corrections; all physical/PG skips remain explicit.
- Client contract suite observed7 failures/2 passes, then its10 cases passed.
- Independent backend review reproduced ordinary SyncService accepting a fake
  session-ID admission. Fixed by barrier-issued authority bound to the live root
  transaction; actor/protocol/org/location/grants/expiry are rechecked. Admission
  inside a releasable savepoint is refused; item savepoints after admission remain.
- Review also identified concurrent cross-org global-ID collision escaping the
  savepoint, schema guard missing from operator control, and restore/Compose
  ordering gaps. Per-item collision recovery, exact0010 guard, isolated rotation
  before reopening, and explicit default-false Compose mapping resolve them.

Backend independent review at local merge `fa2e5f0` found no remaining source
blockers after committed fixes `86217c4`/`93c49f8`. Independent evidence:508
focused tests passed/33 explicit skips; final targeted rerun122 passed/6 skips.
Frontend independent review and exact integrated aggregate are tracked separately.

## Executable gates and evidence limits

The test catalog includes:

- Fourteen HTTP writer ingress at both floors and exact absent/0/1/unknown headers,
  duplicate/header ambiguity refusal, capability spoofing refusal and exact full
  DB snapshots on rejected writes;113 cases passed locally.
- Missing/current/mismatched/malformed signed incarnation at both floors through
  me/context/sync/admin/inventory and distinct baseline authentication; restore
  counter collision, fresh login and stale baseline family refusal.
- Complete proof matrix, literal canonical vectors, byte/depth/number/timestamp
  bounds, changed full commands, partial/corrupt metadata and independent saves.
- Empty/historical migrations and unchanged old values, append-only audit guards,
  unconditional downgrade refusal including active/proven receipts, recovery CAS,
  rollback and true-empty bootstrap serialization.
- Real PostgreSQL cases for writer-first/floor-first/rollback, actual two-process
  requests and transitive blocker graphs, independent organizations, post-wait
  expiry, cross-org unique-ID collision with sibling preservation, and logical
  restored-counter collision via actual recovery command code.
- Genuine context/start/activation support/incarnation agreement, disabled-support
  epoch invalidation, ordinary isolated client READY/reuse with actual HTTP, and
  a new separate native Chromium case without response rewriting.

Local platform sweep:1458 passed/187 explicit skips before the final schema and
client reconciliation. Integrated core335/335 and API-client1/1 passed. Ruff,
Python typing, generated contracts and selected new regressions passed. A later
full Python sweep exposed the still-old active quote reservation; that metadata
was corrected to0011, then root repository tests107 passed/1 PG skip. The final
aggregate is intentionally still pending at this record's first commit.

No PostgreSQL server/client/Docker or safe configured PG URL is present locally.
Native Chromium is blocked before execution by the environment's socket policy.
SQLite, fake IndexedDB, compilation, collected tests and source review prove no
PostgreSQL/native-browser/installation behavior. Exact-head hosted PG and native
artifacts must clear these gates before B qualification. Physical Windows/Android,
screen readers, actual installation and realistic restore remain separate gates.

## Operator and release boundary

Follow [cutover operation](../07-operations/2026-10-14-server-cutover.md) and the
updated [restore runbook](../07-operations/2026-10-14-backup-restore.md). All old API,
CLI and business-worker binaries must be replaced/drained before relying on B;
no schema/header can fence a binary that never checks it. Supported rollback keeps
B's schema/identity/floor/proof rules. Never lower the floor, erase proof/history,
blindly replay old-incarnation commands or reopen a restored floor0 database.

A qualified code-development MVP does not imply a deployed/installed workshop,
physical V0.1 acceptance or complete money/parts/purchasing product scope.
