# Inventory catalog page filter: rebuilt candidate

## Scope and invariant

Continue the explicitly requested bounded Workshop/inventory flow on verified
PR99 main `6a81c90c9cb2b1ae6d7e406a7bea29519c944660`, tree
`f10f572bfab9b2b4bcd720c748d9fef20346d340`. V0.1 remains partial;
this independently bounded convenience increment does not admit a new domain.
FR-INV-001 remains partial. The accepted connected-inventory ADR and its authority,
privacy, live paging and connected-only boundaries remain unchanged.

A native labeled search filters only the current catalog page by literal
case-insensitive name or SKU substring, trimming surrounding whitespace.
It does not search other pages, IDs, units, stock or movements. Counts distinguish
visible rows from page size; empty page and no matches have distinct explanations.
Reset restores source order and identity. Pagination uses the original unfiltered
50-row receipt. Product selection keeps the existing controller and focus path;
hiding a selected row does not clear independently received details or freshness.

The filter is volatile component state, not persisted or synced. Catalog loading,
access loss/offline and scope invalidation unmount it. Catalog-array replacement
synchronously resets the query; unrelated stock/history updates retain it.
No new API, schema, migration, dependency, grant, write or automatic request.
No new ADR is needed for this presentation projection. Existing theme tokens,
44px/56px density-scoped targets, plain-text escaping and polite counts remain.

## Historical source loss and fresh evidence boundary

Earlier local commit `25684a583d7c617f7c20b47998175b0a14149546` and tree
`b617cfa5163fc11e73766891a60de5f84bedd509` became unavailable after the execution
environment changed. The checkout, exact Git object and logs were absent from
all accessible local repositories. It was not pushed or preserved durably.
This candidate was reconstructed from the prior implementation context on a fresh
clone after verifying remote main. **Old checks do not qualify reconstructed source.**
No byte-identical recovery or reuse of the lost tree's acceptance is claimed.
Fresh RED/GREEN, full aggregate, frontend, static and documentation checks are
required for this new tree, followed by independent review and hosted qualification.

The coordinator's [PR99 receipt](https://github.com/IzignaMx/open-cycling-workshop/pull/99)
records that baseline's CI42919680440: ten checks, aggregate 27/27, 137 browser
cases, Python 6,727 plus 58 exact skips and independent inventory/branding review.
It supersedes prior PR99 pending integration only for that baseline, not this
candidate. Initial PR99 CI42894474317 failure remains historical. Original main
CI42556226651 unknown case/cause remains unexplained; later passes do not resolve it.

The user authorized publication of this improvement and its tests in a new PR,
conditional integration after review/CI, and fresh-main CI verification. This
record is not a publication, merge, deployment or physical acceptance receipt.

## Fresh verification plan and limits

Fresh tests-first proof: a no-filter stub produced two expected behavioral failures
and two passing controls. Implementation then passed those cases. Added rendered
component tests cover labeled search, count/page boundary, selected state,
empty/no-match explanations and HTML escaping. CSS regression preserves the
Workshop density selector on both search and select controls.

Existing seeded floor-zero/floor-one browser journeys cover name/SKU filtering,
keyboard reset, unchanged details, stock-refresh query retention, no filter requests
and pagination resetting query. The preservation journey checks query removal
offline. Collection/typechecking is not executed hook lifecycle or browser evidence.
No browser navigation restriction may be bypassed. Actual lifecycle, pixels,
assistive technology, dedicated PostgreSQL and physical tests require separate proof.
No new unseeded fixture IDs, authentication traces or screenshot policy changes.

Frozen dependencies are installed without changing lockfiles. Local tools use
pnpm 11.25.0 rather than pinned 11.17.0 and Python 3.13.5. Existing large-chunk build
warning is not changed. Final actual counts and environment blockers follow below.
No physical Windows/Android T1–T8/R01-T035, capacity/M2 or real-data restore claim.

## Retained initial rebuilt aggregate

The first rebuilt aggregate failed because the depth-one clone did not contain
pinned legacy fixture commit `714342c60f4163c7b4c1ebec8433995dccbeea01`.
Current PWA build passed; the legacy fixture build could not resolve its tree,
and the browser stage failed downstream. Python 6,101 passed plus 685 environment
skips (12 warnings, 392.53s), and frontend 1,425 passed. This is a retained failed
aggregate, not accepted as green. The exact pinned commit was fetched from origin
without source changes; its tree is `fbf5e5678188a97b8b9709e6f91cb6b250e20c9f`.
Fresh affected build and full aggregate results are required after that repair.

## Completed fresh reconstructed-source checks

- Second full aggregate: **partial**, 21 passed, zero failed, five environment
  blockers. Python 3.13.5: 6,101 passed, 685 environment skips, 12 warnings
  (393.83s). Frontend: 1,425 passed, zero failed/skipped; API-client: one passed.
- Focused inventory: 54 passed. Repository contracts: 201 passed. Both were run
  on this reconstructed source, not inherited from the lost commit.
- All-repository ESLint, touched Ruff/Prettier, normal/offline web TypeScript,
  inventory E2E TypeScript, repository verifier, OpenAPI/types and production
  PWA build passed. Pinned legacy build passed reproducibility after the fetch.
- Independent reconstructed-source review found no blocking findings and ran
  11 passing catalog/panel tests plus clean diff check. Real lifecycle remains
  pending; SSR and authored tests do not substitute for browser execution.
- All 17 inventory browser cases were collected, not executed. Blockers remain:
  missing PostgreSQL test/E2E configuration, unavailable Docker and psql, and
  managed Chromium policy blocking navigation for the 100k spike. No bypass.

Receipts are local ignored artifacts: `artifacts/inventory-rebuilt-qualification.json`
retains the initial failure; `artifacts/inventory-rebuilt-final.json` records the
second run. Git metadata identifies base HEAD with uncommitted candidate changes;
it is not a new acceptance of the base. Production and tests were frozen before
this final run; only evidence stamps follow, with documentation checks rerun.
No hosted qualification, publication, merge, deployment or physical acceptance is
claimed here. Preserve this candidate durably before any environment change.
