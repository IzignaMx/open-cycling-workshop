# Local order queue filters

## Scope and invariant

On accepted PR98 main `039669c5c9c9c0987922f72ee9d54c51ce80cf93`, the next
bounded workshop-flow increment adds exact state and priority filters to the
existing local order queue. They combine with the existing trimmed,
case-insensitive problem/identifier/state-label search. Clearing filters restores
the supplied queue, preserving record identities and its existing ordering.

Reception can isolate orders waiting for parts and urgent work before consulting
the existing connected inventory. This does not connect an order to stock, reserve
or consume stock, or make inventory available offline. FR-SVC-004, FR-SVC-005 and
FR-SVC-012 remain partial; the change is a read projection of existing admitted
records, not a new domain workflow or acceptance of V0.2.

No schema, migration, API, permission, journal, dependency or workflow changes.
No new ADR is needed for transient view-only filters. The runtime continues to
own admission, scope and transition protection. Filters are not persisted and
may reset when the view is replaced or the page reloads. They never confer access.
Native labeled selects and a reset button retain keyboard semantics; result
counts use the existing status region. An order leaves a state-filtered list when
its current projected state changes.

## Baseline evidence boundary

The [PR98 receipt](https://github.com/IzignaMx/open-cycling-workshop/pull/98)
records integration and fresh-main CI42753665376 acceptance. Its source-authored
pending-publication entries remain historical. That receipt does not qualify
this new candidate. Original main CI42556226651 retains an unknown case/cause;
no later pass identifies or resolves it. No workflow rerun is requested.

## Verification

Tests first: missing helper initially failed import. After extracting the existing
search unchanged, nine focused tests produced five expected behavioral/rendering
failures and four passing controls. Final helper and controls then passed.

The retained tests cover exact state versus a misleading problem description,
priority/state/search intersections, empty and unmatched results, stable order and
identity, old search behavior, and actual read-only component markup. The new
Playwright journey covers offline combinations, reset, no journal writes caused
by filtering, and an order moving out of the current filtered state after a local
transition. Collection alone is not browser execution evidence.

Final validation counts and any runtime blockers are recorded in the completion
receipt. Required exact-candidate hosted CI remains separate. V0.1, physical
Windows/Android T1–T8/R01-T035, M2/capacity, real-data restore and deployment
remain unqualified by this work.

## Completed local checks

- Full frontend: 1,418 passed, zero failed/skipped (Node 24.22.1).
- Focused filter and history rendering tests: 48 passed.
- Final repository contracts: 200 passed. The old checkpoint assertion was moved
  to its historical key without removing any failure/scope assertions.
- Web TypeScript, touched ESLint/Ruff/Prettier, clean diff and production PWA build
  passed. The existing large JavaScript chunk warning remains.
- New Playwright case collected successfully. Launch probe fails because this
  environment lacks the required Chromium executable; no browser pass is claimed.
- Independent source review accepted the bounded change with no blocking findings.
  Its independent executed check was clean diff, not a duplicate full suite.
- Frozen dependencies installed without changing lockfiles. pnpm 11.25.0 was used
  locally rather than repository-pinned 11.17.0; Python is 3.13.5.

The first aggregate process was interrupted without a final receipt. Its outcome
is not accepted; a fresh final-tree aggregate is required before publication.

The first completed aggregate found two missing explicit select-event annotations
in the repository's offline TypeScript build (normal web TypeScript passed).
Python passed 6,100 with 685 environment skips and 12 warnings; frontend passed
1,418. The annotation-only correction preserves behavior. The failed aggregate
is retained as failed, not reclassified; final aggregate verification follows.

## Corrected-candidate completion receipt

Final aggregate: **partial**, 21 passed, zero failed and five explicit environment
blockers. Python: 6,100 passed, 685 environment skips and 12 warnings. Frontend:
1,418 passed, zero failed/skipped; API client one passed. Offline TypeScript,
contracts, lint/format, mypy and production PWA build passed. The five blockers
are PostgreSQL test URL, Docker, PostgreSQL tools, managed Chromium navigation
policy for the IndexedDB spike, and the dedicated browser E2E database URL.
No policy bypass was attempted. Missing Playwright Chromium remains the separate
launch-probe result. Neither probe establishes a browser test pass.

Independent review accepted the explicit event-type correction and reran offline
TypeScript plus clean diff. Final documentation stamps are checked separately
with the 200 repository contracts and formatting. Aggregate git metadata records
base HEAD plus uncommitted candidate, not acceptance of the base or a future SHA.
Publication is authorized; exact-candidate hosted/browser qualification and any
integration are still pending. No deployment or physical acceptance follows.
