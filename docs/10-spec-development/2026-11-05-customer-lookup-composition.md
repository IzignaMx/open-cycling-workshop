# Customer lookup: preserve input-method composition

## Admission and invariant

This is a bounded keyboard correction to the shipped local customer-name picker,
not new search breadth. It continues the independently admitted
FR-CUS-002/R02-T001 prerequisite and ACC-002 keyboard operability under the
Foundation's Internationalization Ready principle and UX sections 18–20.
V0.1 remains partial; R01-T035 and physical T1–T8 remain blocked.

An Enter event used to confirm input-method composition is not an explicit search.
The picker must not cancel that input-method action, start lookup, submit an order,
change the selected customer or discard the intake draft. A later ordinary Enter
must still prevent implicit form submission and start exactly one existing bounded
lookup when not busy. Existing explicit buttons and all authority, paging,
single-flight and draft-recovery boundaries remain unchanged.

## Smallest implementation and tests-first plan

The existing handler treats every Enter identically. Three real-component handler
tests were observed RED: composing=true/keyCode=13, composing=false/keyCode=229,
and composing=true/keyCode=229 all incorrectly prevented the default action.
Independent extraction of the existing handler also observed an unwanted search.
These are synthetic handler observations, not actual OS input-method acceptance.

1. In the existing Enter branch, return before prevention/search when the native
   event reports active composition or the legacy composition key code 229.
   The latter protects event sequences where the composition flag is already false.
2. Extend the existing deterministic component host and static type shim to model
   those native event fields, retaining ordinary Enter defaults.
3. Prove all three combinations in idle and busy states, unchanged query/selection/
   intake fields, other-key no-op, and subsequent ordinary Enter behavior.
4. Extend the existing offline PWA journey with synthetic native DOM events,
   preserved draft/selection/journal and later ordinary Enter search.
5. Run focused and full local suites, static checks/build and independent review.
   Obtain exact-source hosted qualification before acceptance or merge.

No ADR, schema/index/API change, query persistence, dependency update, credential,
server permission, or broader V0.2 implementation is needed. No seventh M2 run,
capacity replay, deployment, Pages change or physical acceptance is authorized.
SPENT40927223929 and UNKNOWN41011497919 remain unchanged.

## Accepted baseline and evidence limits

PR89 merged as `d39128b820b5d94b26a8d4c0cda1670957141c40`.
[Main CI 41925254203](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41925254203)
reports successful Python and verify jobs. Its source-bound log records 6,292
Python passes plus 58 intentional skips, 1,296 frontend passes, one API-client
test, 133 direct and 133 aggregate browser passes, repetition groups 20/9/5/10,
14 isolated kernel cases and successful expiry/aggregate gates.
The job checkout and aggregate receipt name that exact main SHA.

This reconciles the earlier local-only PR89 checkpoint, preserving all five failed
historical CI runs and their uncertainty. It is a baseline receipt, not evidence
for the changed composition handler. Large browser archives were not downloaded
or byte/trace/screenshot reviewed. Native synthetic event coverage does not prove
physical keyboard, OS IME, Safari or Android behavior.

## Current verification

Three focused behavioral RED failures are retained locally under
`artifacts/lookup-composition/red.log`. Final local Python passed 5,680 tests with
671 environment-dependent skips and 12 warnings in 358.80 seconds, exit zero.
Product and contract source preceded that run; only the final documentation stamp
followed. Frontend: 1,299 passed, zero failed/skipped; API client: one passed.
Focused lookup: 24 passed, independently rerun; an independent actual-component
matrix additionally passed eight idle/busy event cases with nonempty selection
and intake. No blocking review findings remain.

Full Ruff/ESLint/Prettier checks, strict web/offline/native-test types, Python mypy
(124 source files), OpenAPI/generated-client contracts, repository contract and
production PWA build passed. The existing chunk-size warning remains. Repository
tests passed 190 before the stamp and are rerun after it. Locked dependencies were
installed without lockfile changes; local tools were Python 3.13.5, Node 24.22.1
and pnpm 11.25.0, not the separate hosted image's tool receipt.

The changed PWA case was collected and typechecked, not executed locally.
A separate disposable actual-React Chromium probe failed at launch with socket
creation denied and a crashpad initialization error, before browser assertions.
No retry or browser security change followed. Local secret-policy qualification
also could not start because Docker is absent. Those are explicit local limits;
hosted browser, PostgreSQL, runtime and security qualification are still pending.

Evidence logs are under `artifacts/lookup-composition/`, local ignored evidence,
not tracked public downloads. Nine changed paths; none triggers the M2 laboratory
workflow. Fresh CI must qualify this exact source before merge; accepted PR89
evidence cannot substitute for that check.
