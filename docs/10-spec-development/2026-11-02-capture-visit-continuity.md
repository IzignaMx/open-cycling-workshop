# Capture visit continuity · 2026-11-02

Status: **implemented locally; hosted/browser evidence pending**. V0.1 remains
partial. Local verification is not native-browser proof, publication permission
or a release. The source implementation plan retains the detailed test ledger.

## Prior accepted source: PR78, not this increment

Baseline main: `b88c4eee78d0603bb47368bcec83cd9567eac495`.
The coordinator supplied the prior independently accepted
[PR78 receipt](https://github.com/IzignaMx/open-cycling-workshop/pull/78):

- Fresh-main [CI41372646038](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41372646038),
  aggregate artifact 13110609454: 27/27; Python 5,556 passed + 58 expected skips;
  frontend 1,050 and API client 1.
- Browser direct 105 / aggregate 105; repeats 20/9/5/10 and kernel 14.
- Runtime 41372645960, Security 41372646069, micro 41372645988 and preview 41372645954:
  all accepted on attempt 1 with CI.

Provenance is the coordinator's retained acceptance summary; archives were **not redownloaded**
by this documentation worker. These are named-source receipts, never proof for new
visit-continuity code. They supersede PR78's source-authored pending hosted/main
notes; original reconstruction failures and local browser limitations remain history.
The prior mounted-form late-receipt fix is not reopened as a failed requirement.

## Bounded selected behavior

The [design](../superpowers/specs/2026-11-02-capture-visit-continuity-design.md) and
[plan](../superpowers/plans/2026-11-02-capture-visit-continuity.md) address automatic
same-scope verification in a single controller visit. The controller-owned volatile
customer/order drafts, clean defaults, edit identities and pending/UNKNOWN protection
must survive genuine masking/unmount, then return only after matching fresh READY.
Private DOM does not remain mounted. Old handlers and stale attempts cannot become
current authority. Explicit logout/change/dispose closes the visit. Scope mismatch
irreversibly removes private values and cannot resurrect them through A→B→A;
unresolved work retains only generic capture-only denial as specified.

No persistence schema, kernel/repository transaction, backend, permissions, financial
replay, workflow, module or deployment change is implied. Retained values are not
an automatic retry instruction. Masking, absent journal rows or similar values do
not prove rollback or identify an uncertain attempt.

## Traceability and evidence boundaries

Phase 1 FR-CUS-001 → canonical R01-T030 and FR-SVC-001 → canonical R02-T005 retain
**partial** ledger rows. Those canonical tasks are broader than this correction.
The existing requirement/task pairs are updated, not duplicated or renamed.
Phase 4 UX §22 and OFF-001 motivate this continuity slice; OFF-007/full reload and
recovery requirements are not closed by volatile state.

`apps/web/e2e/capture-visit-continuity.spec.ts` is the authored actual-PWA evidence
path. Authored/collected tests are not executed browser proof. Preserve both prior
late-receipt journeys and real remount/privacy/unknown/pending/default behavior.
Six native-browser cases are collected, with zero executed locally. Functional
reproduction uses the actual controller/App callbacks with simulated hooks and
reconciliation; it is not native React proof or evidence of persisted duplicates.
Documentation contracts distinguish the new pointer from preserved historical
source blocks and retain unique canonical mappings. Static checks cannot qualify
runtime, PostgreSQL, native React, physical devices or accessibility.

## Fresh local verification

- Seven lifecycle regressions reproduced RED before implementation and now pass;
  six voluntary-leave regressions also followed RED → GREEN.
- Final frontend core: **1,119 passed**, zero skips/failures. Normal/offline
  typecheck and production PWA build passed; the existing bundle-size warning remains.
- Full local Python: **4,946 passed, 671 skipped, 12 warnings**. Missing PostgreSQL
  and native-service prerequisites are not treated as accepted hosted skips.
- Independent bounded source/design review accepted: 60 integration/retained plus
  38 owner tests passed; three safe copied-loader mutations caused 12/18/4 failures.
  The misleading closed-empty pending notice was fixed with its own RED/GREEN test.
- Whole-repository Ruff/format, mypy, ESLint, generated OpenAPI/client and repository
  checks passed. Documentation contracts and repository tests also passed.
- Local evidence is retained under `artifacts/capture-visit/`; it does not qualify
  the exact future hosted candidate or fresh main. No deployment was performed.

## Still open and authorization boundary

- Native-browser execution and exact-source hosted/fresh-main qualification.
  Independent local source review is accepted; hosted evidence review remains pending.
- Separate explicit publication/integration authorization; no prior approval carries over.
- Full reload/crash recovery, durable capture-intent/batch correlation and persistence.
- Physical T1–T8, R01-T035, trusted installation, storage, recovery and capacity.
- Historical cleanup 41011497919 remains UNKNOWN. Ownership 40927223929 is spent;
  no consumed experiment replay or workflow identity rotation.
- Pages remains at source 3c6513d; no deployment occurs here. PR59 source-qualified
  full-history validation remains preserved; actual-installation recovery is separate.
