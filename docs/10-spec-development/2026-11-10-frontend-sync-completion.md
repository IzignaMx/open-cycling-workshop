# PR98 automatic-sync completion follow-up · 2026-11-10

Status: **locally verified and independently reviewed; publication and new hosted qualification pending**.
Base PR98 head `92aa310a4245f14166fc5ca879db44b78291587d`, tree
`7a4519c0151d0e40c0446490c0b14c024c6ad9e9`.

## Observed attempt and separate evidence boundaries

[PR98](https://github.com/IzignaMx/open-cycling-workshop/pull/98) published the exact
reviewed diagnostic tree. The maintainer authorized its publication, necessary
CI correction, integration only after review and checks pass, and fresh-main
verification. This supersedes the historical local publication-pending fields,
not any qualification, physical, capacity or deployment gate.

[CI42572334394](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42572334394)
failed on attempt one. The direct frontend run identified the test “successful
automatic verification overrides stale false hint before new baseline dispatch”
at `apps/web/tests/runtime/controller.test.mjs:1066`: expected `synced`, observed
`syncing` (1,402 passed, one failed). The controller source and this test were
unchanged by the diagnostic increment. Captured requests reached authentication,
context, baseline start/page/finalize, initial delta, activation validation,
mutation dispatch and one post-mutation delta.

The later aggregate frontend run passed all 1,403 and emitted the new bounded
structured diagnostic report. It does not cancel the direct failure. Aggregate:
23 passes, two not-executed failures (PWA/browser fixture handoff refused), one
IndexedDB blocker after browser installation was skipped. Browser, kernel and
20/9/5/10 repetitions were unrun, not qualified. The inventory repetition proof
explicitly records incomplete; the legacy archive contains only its manifest.

The same attempt passed source-bound Python/PostgreSQL 6,725 cases plus 58 exact
intentional skips, zero unrun, with complete coverage and both container-cleanup
records verified. DCO, Security, microfixture, all six runtime jobs, inventory
and branding receipts passed within their stated limits. Artifact bytes/digests
were checked. Build-resource cleanup was not assessed. These passes do not accept
PR98 or qualify a later correction.

The original main [CI42556226651](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42556226651)
remains failed on its first attempt. Its failing case and cause are **unknown**
and **not resolved**. The new identified case does not recover that lost evidence.
No failed workflow has been rerun.

## Bounded corrective work

The old test drained a fixed 20 × 100 `setImmediate` callbacks and ticked mocked
zero-delay timers, then asserted completion. That counts event-loop turns rather
than awaiting asynchronous network, storage and cryptographic work. The runtime
intentionally schedules another zero-delay sync after an APPLIED pass, and only
publishes `synced` after the following idle pass completes.

A controlled held response can test that completion assumption independently of
runner speed. Both authority variants, stale false network hint, automatic
verification, delivery acknowledgement, immutable journal and authority-before-
dispatch assertions must remain. The correction is confined to tests and their
completion/cleanup logic. Production, permissions, wire contracts and the reviewed
diagnostic implementation remain unchanged. The controlled RED held a post-mutation delta response with the old fixed drain:
both authority variants failed `syncing` versus `synced`. The changed-authority
request sequence matched the observed PR98 sequence. This proves the old test's
completion assumption is invalid under delayed work; it does not establish the
exact scheduling of that hosted attempt or identify the old main failure.

The replacement waits for observable `synced`, yielding while ticking only timers
already due. A monotonic five-second deadline bounds failure. It adds no network
retry, manual sync, sleep or advancement of nonzero retry deadlines. Four delayed
variants cover both the APPLIED and following idle pass for both authority forms.
While held, they require `syncing`, durable applied delivery and an unresolved
completion wait. After release, they retain all original assertions and require
the two post-mutation delta passes.

A cleanup review concern was separately reproduced: the earlier helper could tick
once after teardown. The final helper checks cancellation before and after yielding;
the caller observes rejection immediately and always aborts, releases the held
response and drains completion in `finally`. Two additional permanent controls
require cancellation before the next tick and timeout as failure.

## Current focused validation

Final controller-test SHA-256:
`4cdd13d773ff06bca897816f8185f70880807791d4282764f0cc635ed8f148d3`.
Exact Node 22.16.0 and pnpm 11.17.0, frozen dependencies. Eight focused cases and
the complete frontend (1,409 passed, zero failures/skips) passed. Touched ESLint,
Prettier and whitespace checks passed. No production or diagnostic-source hashes
changed.

Three deliberate negative controls each produced exactly four expected failures
under strict unhandled-rejection handling: substituting the old finite drain,
injecting an early gated assertion failure, and an immediate completion timeout.
No unhandled-rejection or late-activity warnings occurred. These are sensitivity
and cleanup controls, not candidate-suite failures or hosted retries. Temporary
control files were removed. Independent review accepted the exact frozen source with no remaining blockers: a
separate runtime TypeScript compile and all 161 controller cases passed under
strict rejection handling, zero failures/skips. The negative controls were inspected
without duplicate execution. The final local aggregate below covers the frozen correction; these results
do not qualify the corrected candidate in hosted CI.

## Final local aggregate

On Python 3.13.5 and Node 22.16.0, 21 checks passed, zero failed, with five explicit
environment blockers. Python passed 6,099 cases plus 685 environment skips and
12 warnings in 363.78 seconds. Frontend passed 1,409 through the structured reporter
with diagnostics available; API client one passed. Runtime HTTP smoke, PWA build,
Ruff, format, mypy (126 source files), ESLint, Prettier and OpenAPI/TypeScript
contracts passed. PostgreSQL integration, Docker CLI, PostgreSQL tools, IndexedDB
100k (managed Chromium URLBlocklist) and browser E2E remain locally blocked.
No managed browser restriction was bypassed.

This full run used the uncommitted correction on base head
`92aa310a4245f14166fc5ca879db44b78291587d`; that base appears in aggregate metadata.
It is not acceptance of the failed base run. Implementation and test hashes were
frozen and verified unchanged after the run. Only evidence wording was stamped
afterward; all 199 repository tests passed again against the final documentation.
The corrected PR source still requires its own hosted checks and fresh-main proof
if subsequently integrated. Neither recorded failed attempt has been rerun or
retrospectively accepted.

V0.1 and FR-SVC-016/R02-T013 remain partial. Physical T1–T8/R01-T035 remain omitted,
not accepted. M2/capacity, deployment and real-data restore remain outside scope.
SPENT40927223929 and UNKNOWN41011497919 remain unchanged.
