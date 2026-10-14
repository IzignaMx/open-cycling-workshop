# Isolated offline identity kernel · 2026-10-14

Status: `first_head_hosted_verified_reconciliation_pending`; implementation and
independent review complete for the isolated boundary. Production activation is
blocked by the integration gates below.
Branch: `feat/isolated-offline-identity-kernel`.
Initial base: PR #28 head `1ab3554d`. First reviewed local head:
`1d57c0955c2480868124ea618d7eac739737cc6b`; identical published head:
`668a18f5cf16fc44ce9f4ee24498774ad7049b46`; tree:
`22ef13dd0fa1b1983a1d4d58bb64738d27e9682c`.
Reconciliation uses the published ancestry and true-merges actual main #29
`f87205157e298f5c1c7c3f08d024fe822d84582b`; kernel source stays unchanged and
server source exactly matches that main checkpoint. Fresh combined review/qualification is separate
from the first-head evidence below.

## Bounded delivery

This increment adds an explicitly isolated Dexie v5 factory and identity-bound
local kernel. The [ADR](../02-technical-architecture/2026-10-14-isolated-offline-identity-kernel.md)
records the transactional boundary and future rollout requirements. The local
modules are `apps/web/src/access-kernel/{types,context,operations,projection,database,kernel}.ts`;
`createKernelDatabase(name)` and `AccessKernel` are the isolated entry points.

Production `App`, the default `OcwpDatabase` singleton and the existing Golden
Slice remain on v4 unchanged. New isolated contexts stop at `BASELINE_REQUIRED`;
authentication-context and authoritative complete-baseline integration are not
implemented. `READY` reuse requires an already completed matching partition;
tests seed that future-integration fixture directly. No baseline merge/activation
API or HTTP adapter is delivered. There is no new server endpoint, wire contract, SQL migration,
credential persistence, production activation or actual installation upgrade.
The live UI's pre-existing multi-user cache/replay and offline-permission risks
remain open. This is not a complete administration UI or release qualification.

The additive schema preserves all eight existing stores, including queue,
conflicts, local order events, personal preferences and device-local logos.
Legacy records remain unchanged and unattributed; the new kernel does not adopt
them as an authorized working set or automatically replay them. Authored
operations use an immutable journal and separate durable delivery/history state.
The existing quote Dexie reservation is moved from v5 to future v6; administration
Alembic `0008` and quote PostgreSQL `0009` are unchanged.

## Acceptance and evidence ledger

Evidence below belongs to the first reviewed tree named above. Reconciliation
with main #29 does not relabel that evidence as a fresh combined run. A fixture
exercising ready-state internals is not evidence of a production baseline or live
browser isolation.

| Acceptance                     | Required proof                                                                                                                   | Current evidence                                                                      |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Production boundary unchanged  | Source/contract review; existing Golden Slice regression                                                                         | Source review; unchanged production PWA 23/23 twice                                   |
| New contexts fail closed       | `BASELINE_REQUIRED`, no legacy projection/cursor fallback, no normal activation shortcut                                         | Node tests; native two-tab fixture uses explicit baseline seeding                     |
| Lossless additive v5           | Supported legacy layouts with nonempty queue/conflicts/events/preferences/logos and unknown fields; exact equality after upgrade | Node exact-all-store fixtures; native queue/preferences preservation at five versions |
| Same-workshop author isolation | Distinct principals with identical organization/location/grants cannot read or dispatch each other's journal/cache/event data    | Node tests and native A/B two-tab fixture                                             |
| Transactional fencing          | Stale reads, commands and ACKs after context/epoch/generation switch reject; atomic rollback prevents partial writes             | Node tests; native stale command/ACK fencing                                          |
| Immutable commands and history | Original envelope survives success, retry, rejection and reload; journal/delivery/event writes are atomic                        | Node tests; native original journal preservation                                      |
| Dispatch and dependency safety | Current-author/current-capability selection, unchanged IDs/payloads, dependent holds, independent progress                       | Node tests; no native backlog-performance claim                                       |
| ACK validation                 | Foreign/missing/mismatched IDs, contradictory duplicates, invalid status/version and stale batches acknowledge nothing           | Node malformed-response tests; native stale ACK case                                  |
| Legacy recovery boundary       | No inferred author from login/actor fields, no automatic replay/claim/delete, preserved unknown data                             | Node tests; native no-attribution migration cases                                     |
| Presentation continuity        | Eight existing stores/indexes retained; personal appearance/logo scope unchanged                                                 | Node all-store fixtures; native logo preservation; unchanged PWA suite                |
| Failure and compatibility      | Abort/quota/versionchange/reload cases; evidence distinguishes fake storage from real browser                                    | Node quota/versionchange; native abort rollback and old-writer blocker                |
| Future v6 preservation         | Explicit future-schema fixture, if implemented; reservation alone is not migration proof                                         | Fixture-only emulator proof; no native v6 implementation                              |
| Independent review             | Scope, source invariants, recovery claims and evidence limits reviewed                                                           | Clean final review; focused 60/60 and harness checks independently passed             |

Traceability: FR-IAM-002/004/006/008; OFF-001/003/005–009/012;
NFR-004/005/010/014; SEC-002/003; QA INV-LOCAL-001/GATE-LOCAL-001. Later
production UI integration also requires ACC-002/003/004/008/010 evidence.

## Verification log

- Preflight base: `1ab3554d`; branch `feat/isolated-offline-identity-kernel`.
- Focused regression red: initial absent-module failure, then observed behavioral
  failures for stale logout locking a newer principal, adapter history mutation,
  held same-aggregate dispatch, changed local-event retries, mutated in-flight
  ticket arguments and contradictory projection versions. Each corresponding
  regression passed after its correction. Migration rollback cases execute actual
  Dexie transactions in the emulator; they are not native browser proof.
- Focused command: `node node_modules/typescript/bin/tsc -p apps/web/tsconfig.kernel-test.json --pretty false`
  followed by `node --test apps/web/tests/access-kernel/*.test.mjs`: **60 passed**.
- Integrated `node apps/web/tools/run-core-tests.mjs`: **158 passed** (98 existing
  tests plus 60 kernel/context/migration regressions). The runner also typechecks
  the separate browser harness/config before running the Node tests.
- Migration fixtures: raw native1 plus logical v1/native10, v2/native20,
  v3/native30 and v4/native40 all preserve exact rows on v5/native50. Abort and
  simulated quota rollback, retry, versionchange close and a fixture-only future
  v6/native60 additive store preserve journals/preferences. Node tests use real Dexie with the `fake-indexeddb` emulator,
  not a browser. The dedicated real-browser harness has separate first-head evidence below.
- Real frontend, offline fallback and isolated browser-harness typechecks pass;
  ESLint and isolated Vite harness build pass. PWA build passes with the original
  production entrypoint unchanged. Exact local aggregate at `1d57c095` passed
  21 checks with zero failures and five environment blockers.
- Eight separate native-browser journeys are collected and typechecked, including
  real two-tab fencing, historical schema upgrades, aborted upgrade and the
  observed old-bundle blocker. They run through `pnpm --filter @ocwp/web test:kernel-browser`
  in hosted CI separately from the unchanged existing PWA journeys. Local
  execution is blocked by managed Chromium URLBlocklist policy; no alternate
  browser/flags or policy bypass was attempted.
- Existing Golden Slice and other browser journeys: first-head hosted 23/23
  passed twice; final combined source needs its own hosted run.
- Working-tree aggregate: 755 Python tests passed and 60 explained local skips;
  OpenAPI/generated client, runtime HTTP smoke and Python static checks pass.
  An intermediate run had one formatting failure while the new fixture was being
  formatted. The exact-head rerun above verified its correction. PostgreSQL URL,
  Docker, psql, managed Chromium navigation and destructive browser-E2E database
  configuration remain five explicit environment blockers.
- Independent review reproduced two projection-continuity bugs and an unbounded
  lifetime-journal dispatch scan. Red→green fixes preserve explicitly labelled
  applied-awaiting-authoritative-projection overlays, retain eligible same-author
  old-epoch pending overlays, suppress rejected dependency chains and bound
  dispatch to indexed 100-row metadata pages with durable revisit/wrap behavior.
  Applied history no longer loads into dispatch, and authoritative-covered
  immutable history is excluded from projection reads. The review also prompted
  primitive-string database-name rejection and separate browser trace/report
  artifacts so later production E2E cannot erase isolated-kernel evidence.
  A second review added transitive implicit-aggregate dependency checks and
  bounded reverse projection pages with older-eligible fallback, each observed
  red before its fix. Final independent review at `1d57c095` was clean, with
  60/60 focused tests, harness typecheck/build, eight-case discovery and
  source/test checksums independently verified.
- Exact first-head commit/tree and hosted run/artifact links: recorded below;
  new combined reconciliation evidence remains separate.
- New server/PostgreSQL behavior: not implemented or qualified by this increment.
- Actual installation migration, recovery, production activation and physical
  Windows/Android qualification: not performed.

Historical evidence in other increment records remains historical. It must not
be relabelled as proof of this new v5 boundary. Test discovery is not execution;
static or fake-table evidence does not establish real IndexedDB transactions,
multiple browser tabs, PWA upgrade behavior or PostgreSQL concurrency.

## First-head hosted qualification

PR #30 head `668a18f5cf16fc44ce9f4ee24498774ad7049b46` was tested at GitHub
merge checkout `cd5dd014f8db365156f7372332f240e74c37d833`, whose parents are
main #28 `675fe209fa0b038156ba0c57c44f520b2e2de376` and that PR head. The
checkout and head both resolve to tree `22ef13dd0fa1b1983a1d4d58bb64738d27e9682c`,
verified by fetching the Git objects, identical to the independently reviewed
local tree. These results do not include later main #29 server changes.

- CI [38559830979](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830979):
  qualification **27/27 passed**, no blockers; Python **812 passed, 3 skipped**;
  frontend **158 passed** and API client **1 passed**. Skips are one missing
  matching-major PostgreSQL client restore case and two dialect-specific cases;
  the separate runtime drill below covers its own PostgreSQL 18 restore path.
- Native Chromium **8/8 passed**, with zero skipped/flaky/unexpected and retry 0
  for every case: native1/10/20/30/40 preservation, two-tab fencing, upgrade-abort
  rollback and the old-v4-writer compatibility blocker. This is real execution,
  not test discovery. Node-only quota/full-all-store and future-v6 fixture claims
  remain distinct.
- Unchanged production PWA **23/23 passed twice**, plus **10/10** explicit
  baseline/reconnect repetitions with retries disabled. The PWA still uses v4.
- Runtime [38559830844](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830844):
  **11 checks passed**, including fresh stack, Caddy/offline/reconnect/two-browser
  convergence, persistence and PostgreSQL 18 backup/restore; three ARM64 image
  builds passed. Physical hardware was explicitly not tested.
- Security [38559831014](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559831014)
  and DCO [38559830900](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830900)
  passed. Existing hosted 100k IndexedDB benchmark passed at 38,978.1 ms write /
  99.8 ms count-and-sample read; this is not kernel-backlog/device qualification.

Downloaded artifacts were ZIP-integrity checked and SHA-256 matched GitHub:

| Artifact                                                                                                            | ID          | SHA-256                                                            |
| ------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------ |
| [Isolated kernel](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830979/artifacts/11891389212) | 11891389212 | `8129954009b42a5a3bd92c971f912e97d5b9b2bc7af39558540afbc3b5dba1aa` |
| [Production PWA](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830979/artifacts/11891204257)  | 11891204257 | `03a5efc83b5d904ff1f89f13dcf0cadd184d39e0a7f8c00ab46bac32dd293a14` |
| [Qualification](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830979/artifacts/11891829021)   | 11891829021 | `a3df750b7d25e43436e60bda4c655364bb2114ee5ad4578f13af676c5000cb4d` |
| [Runtime](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38559830844/artifacts/11891083912)         | 11891083912 | `c29f3f37171a999f98ec3fd71f1438530b640a348b81cf82db4153ab7c620ba9` |

## Main-29 reconciliation boundary

The actual-main merge preserves PR #29's same-shape effective `/auth/me`,
server-attributed new transition events and receipt tuple validation. Those
prerequisites do not supply the kernel's verified context/epoch/lease, complete
baseline or original-author/full-payload receipt binding. No server behavior is
reimplemented by this client increment. Kernel source/tests and production
client source remain byte-identical to the first-head tree; combined source
qualification and independent reconciliation review must be recorded for the
new exact commit before publication/merge readiness is claimed.

## Demonstrated old-bundle compatibility risk

The test expecting a v4-only Dexie constructor to reject native50 failed. Dexie
4.4.4/emulated IndexedDB opens that database and can still write its legacy queue.
The replacement test records that behavior as an activation blocker; it does not
claim the compatibility problem is fixed. The unchanged native-browser test
confirmed the same reopen/write behavior in the hosted run above. The ADR
requires explicit old-bundle/client-protocol fencing
and consideration of a separate database name before production integration.
No mitigation is activated in this increment, and unchanged v4 Golden Slice
legacy-replay behavior remains historical production behavior, not a v5 guarantee.

## Next integration and stopping conditions

Do not switch the production singleton until an effective authenticated context,
complete authorized baseline and ordered handoff are integrated and qualified.
That work must cover direct-REST feed gaps, real PostgreSQL commit ordering,
private baseline staging, grant expansion/backfill, contraction, offline expiry,
reconnect-before-push, author-preserving pending overlays and safe old-bundle
handling. Do not turn a fresh login or empty queue into a baseline-complete marker.

Production acceptance must retain the Golden Slice's offline/durability outcome
and add real-browser same-scope A/B switching, multi-tab delayed commits/ACKs,
permission/scope changes, quota/upgrade/reload and recovery tests. Review server
receipt actor/payload binding explicitly; local ownership metadata cannot close
that gap. Administration UI and organization-wide workshop navigation remain
gated on their own integrated isolation and concrete-workshop-selection proof.

The [manual checklist](../../MANUAL-ACTIONS-CHECKLIST.md#2026-10-14--isolated-offline-identity-kernel-and-future-rollout)
keeps the conditional operator boundary open. Server backup excludes local
queues. Preserve legacy originals; no clearing, inferred attribution, automatic
replay or destructive downgrade. Stop affected work on unknown migration impact,
isolation/data-loss failure, attribution ambiguity or missing required runtime
evidence. Continue only independently safe work and record what remains blocked.
