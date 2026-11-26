# Project and inventory status reconciliation · 2026-11-25

Latest source update: [PR122 postmerge evidence, November 26](#pr122-postmerge-evidence--2026-11-26).
The original audit below retains its historical evidence and limitations.

## Source and evidence boundary

Inspected baseline: `3d11bbd3afadaa998063ab637c8eb58caaaba32a`, merged
[PR121](https://github.com/IzignaMx/open-cycling-workshop/pull/121) on November 22.
GitHub PR metadata and local history agree on head
`7f3ad1eab304d57e714225351e6522d59f57a2b6` and the merge commit. This is a
source inventory and current-work index; V0.1 remains **partial**.

The November 20 secure-bootstrap record still described hosted execution as
pending. The subsequent physical-device guide and PR121 body record
[CI44692144993](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44692144993)
for the earlier `491ac31d` tree: 145 direct browser cases. That historical receipt
does not qualify later `7f3ad1e` or merged main. This audit inspected the metadata
and committed documents, not that run's archives. No new archive acceptance or
fresh-main CI success is inferred from merge status. A subsequent GitHub Actions
API lookup of the exact main SHA independently reports attempt-one success for
[CI44997636297](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44997636297),
[Local runtime44997636334](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44997636334),
[Security44997636288](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44997636288)
and [micro44997636260](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44997636260).
The scheduled Security45213022965 run also reports success. These are observed
workflow conclusions, not a fresh independent review of their archives or proof
for the modified successor. The earlier PR-filtered workflow and legacy status
lookups returned no rows because they were incomplete views of Actions evidence.

The same-main verify-job log was also read: it reports frontend **1,805** and API
client **1** passing tests, a passed aggregate, a Python receipt with **6,767
passed / 58 intentional skips** and both shard cleanups, **145 direct browser
passes**, and repeated browser groups of **20 / 9 / 5 / 10** passes. These are
log-reported results for the inspected baseline, not independently revalidated
archive completeness, physical acceptance or the new documentation candidate.

## Documentation reconciliation

The README's current-checkpoint link pointed to the November 1 PR77 record;
execution-state selected November 19 at the top but November 12 in active-plan
and last-checkpoint fields; its next-focus list still began with PR90.
CHANGELOG had no entry newer than November 10. These navigation fields now point
to this audit while preserving the original source-bound records and failures.
A generic repository navigation contract now requires current-checkpoint and
last-checkpoint agreement, an existing evidence document linked by README and an
existing active-plan file. Both stale-checkpoint and stale-README-link controls were observed failing
against baseline documents, then the corrected documents passed all three
navigation checks. This detects stale navigation without asserting release
or runtime acceptance. Historical checklist requests for publication or CI are retained as history;
the current summary does not translate those requests into release acceptance.

The [20-claim matrix](product-description-coverage.json) remains a dated planning
inventory, and [traceability](traceability.csv) remains a bounded evidence ledger.
Neither is a complete runtime qualification. The Foundation, accepted ADRs,
functional requirements and product scope remain unchanged. Missing product
capabilities retain their planned tasks and acceptance criteria.

## Current implementation inventory

| Area                                                    | Inspected source capability                                                                                                              | Remaining boundary                                                                                                    |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Customers, bicycles and service orders                  | Local records, durable journal, scoped sync, editing, intake, queue filters, saved associations and transition notes                     | Full canonical Workshop Core acceptance, existing-bicycle intake selector and safe mixed-version handover remain open |
| Identity and bootstrap                                  | Scoped account administration; browser secure-context check before session access; accessible storage-denial notice                      | Trusted LAN origin and actual Windows/Android behavior require installation/device evidence                           |
| Inventory catalog                                       | Mounted product-create API plus scoped connected catalog UI with current-page name/SKU filtering                                         | No inventory write UI, global catalog search or offline inventory snapshot                                            |
| Inventory ledger                                        | Mounted movement API; append-only adjustment, reservation, release and consumption; available quantity derived from all scoped movements | Stock entry does not establish physical stock accuracy, costing, purchases, suppliers or POS completion               |
| Inventory reads                                         | Scoped stock and movement endpoints, bounded pagination, current authorization and private/no-store responses                            | Dedicated PostgreSQL and native-browser proof recorded below; physical stock and real-device acceptance remain open   |
| Quotes                                                  | Arithmetic/history, immutable persistence/service prerequisites and authority/privacy fences                                             | Quote API/UI remain unmounted; activation, capacity and operational acceptance stay open                              |
| Branding and modules                                    | Four themes, shared branding, M0 descriptor and M1 reference information                                                                 | Full white-label outputs and installable third-party SDK/runtime are not complete                                     |
| Operations                                              | Source-built Compose candidate, backup/restore tooling and historical hosted runtime receipts                                            | Actual installation, trusted LAN, local-journal recovery, physical devices and release qualification remain open      |
| Purchases, sales, agenda, staff, metrics and automation | Requirements, canonical phased tasks and acceptance mapping; internal outbox/jobs foundations                                            | These business workflows remain planned or partial; no completed feature is inferred from a source placeholder        |

The inventory source of truth is
[`inventory/router.py`](../../services/platform/src/cycling_workshop/inventory/router.py),
[`inventory/service.py`](../../services/platform/src/cycling_workshop/inventory/service.py),
the [server module contract](../../services/platform/src/cycling_workshop/inventory/README.md)
and [connected UI contract](../../apps/web/src/features/inventory/README.md).
Consumption finalizes the hold and appends its physical issue atomically; a
movement page alone cannot reconstruct availability. Inventory remains connected
only under the accepted [read ADR](../02-technical-architecture/2026-10-15-connected-inventory-read.md).
Products are bound to one location and SKU uniqueness is organization-wide; the
current scoped balance does not establish a shared multi-location catalog or
stock transfers. No real workshop database or physical item count was supplied or inspected here;
this checks inventory software, not a customer's stock balance.

## Inventory requirements retained

| Requirement             | Source state and remaining work                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| FR-INV-001              | Partial: SKU/name/unit exist; variants, EAN and categories remain                                                                     |
| FR-INV-002              | Scoped balance at the product's bound location exists; full multi-location catalog and transfers remain                               |
| FR-INV-003 / FR-INV-004 | Movement-based changes and ledger-derived availability exist; source invariants do not complete the inventory release                 |
| FR-INV-005 / FR-INV-006 | Minimum stock/alerts and cost/price/margin remain                                                                                     |
| FR-INV-007 / FR-INV-008 | Suppliers, purchase orders and partial receipts remain                                                                                |
| FR-INV-009 / FR-INV-010 | Named return/damage/loss/donation/reuse and physical-count workflows remain; generic signed adjustments do not qualify these journeys |
| FR-INV-011 / FR-INV-012 | Non-stock products/services and extensible compatibility remain                                                                       |

These are the existing [Phase 1 requirements](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md)
and canonical V0.3/V0.4 plan, not exclusions or newly reduced acceptance criteria.

## Current work and verification

Inspect inventory correctness and documentation consistency against this baseline,
preserving authorization, ledger history, integer quantities, privacy and the
existing online-only boundary. No inventory defect was reproduced in the bounded
source audit and nearest regression suite. The baseline inventory
Python suite ran on November 25: **456 passed, 64 skipped** in 30.00 seconds,
with one existing Starlette/httpx warning. All 64 skips require unavailable
PostgreSQL execution in that initial run; the separate real-database proof below
supplies scoped evidence rather than turning those skips into passes.

A dedicated PostgreSQL **18.4** test database subsequently passed the existing
inventory read proof: **43/43 cases, zero skips**, including the guarded
**20,001-product / 100,000-movement** fixture (35.56 seconds). Evidence is retained at
`artifacts/inventory-read/pg-direct/`. Current production PWA and reproducible
pinned-legacy builds also passed with Node **22.16.0** and pnpm **11.17.0**.
These synthetic source checks do not inspect real workshop stock or qualify
physical storage, workload capacity or deployment.

The PostgreSQL command/migration/write-authority selection passed **104/104**
cases with zero skips (17.80 seconds); it includes the remaining **21** database
cases skipped by the initial suite. The 104-case selection overlaps the initial suite; these invocation counts
are reported separately and must not be summed as unique test cases.

The native Chromium inventory journey passed **17/17** cases in 51.4 seconds,
with **zero retries, one worker**, including four-theme accessibility/reflow,
page filtering, stock/history, scope changes and offline clearing/preservation.
The dedicated PostgreSQL container was removed and its absence confirmed after
testing. This synthetic runtime is not a deployment or Windows/Android result.
The full repository contract suite passed **226 tests**, including the focused
documentation and product-description contracts; the repository verifier passed. Test collection or source
inspection alone does not qualify behavior. The independent source review found
no blocking findings in the navigation tests and documentation.

The broader local verifier reported **21 checks passed, two failed and three
blocked**. Python passed **6,140 tests with 685 environment skips**, frontend
**1,805/1,805**, and API client **1/1**; lint, formatting, typechecks, HTTP smoke
and generated contracts passed. This invocation collected Python before the
three new navigation tests were added; the final 226-case repository run includes
them. The two failures share one preparation cause: the inherited Node 24.22.3 /
pnpm 11.25.0 tooling did not satisfy the archived client's pnpm 11.17.0 pin,
so its build failed and aggregate browser execution did not start.

The affected verifier function was then rerun with Node **22.16.0** / pnpm
**11.17.0**: current and reproducible historical builds passed. Its full browser
suite remains blocked on a dedicated E2E database, separately from the successful
17-case inventory invocation above. The initial aggregate also lacked the general
PostgreSQL test URL and psql client; its 100k IndexedDB probe reported the managed
Chromium navigation policy as a blocker. No policy was changed or bypassed.
Preserve `artifacts/audit-20261125-baseline.json` and
`artifacts/audit-20261125-build-correction.json` as separate local receipts;
the initial aggregate is **not retroactively passed**. The full release suite,
physical qualification and exact successor hosted CI remain separate gates.

## Remaining gates and next work

1. Qualify the exact documentation/navigation-test candidate through normal CI
   and independent review; the inventory source itself remains unchanged.
2. Continue V0.1 correctness/recovery work when concrete evidence exposes a ready
   task. Preserve the full product matrix; do not drop future inventory, purchasing,
   sales or scheduling requirements because their dependencies remain open.
3. Complete physical T1–T8 and R01-T035 with the actual Windows/Android equipment
   and operator, using the [manual action guide](../11-device-qualification/2026-11-20-windows-android-manual-actions.md).
4. Identify a real deployment target and prove its installation-specific backup,
   restore, trusted origin and device behavior before claiming an operational
   deployment. GitHub Pages is the static presentation at source `3c6513d`,
   not a workshop server.
5. Preserve G1–G6, quote activation/capacity, historical cleanup `41011497919`
   **UNKNOWN** and measurement `40927223929` **SPENT** as distinct gates.
   This reconciliation does not rerun consumed experiments or authorize loss of
   data, historical evidence, local drafts or pending mutations.

## PR122 postmerge evidence · 2026-11-26

The documentation/navigation-test candidate was merged as
`810a4623a64c28d1abf0e40454129df780adb328` in
[PR122](https://github.com/IzignaMx/open-cycling-workshop/pull/122). Candidate head
`d1d24d7cce0ff642041e2a855bde7361487d95c8`, its tested synthetic merge
`da346145cee3a0435cdd31d1374ef0f8cd00625f`, and merged main have the same tree.
The successor's hosted-pending statements above are historical; this receipt
supersedes them only for that exact source, not later edits or release acceptance.

Fresh-main [CI45549103908](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45549103908)
completed successfully. Its Python and verify jobs report successful steps,
including both Python-shard cleanup gates, actual inventory PostgreSQL/Caddy
checks, branding restore, current/historical PWA builds and browser execution.
The reviewed logs report **6,770 Python passes / 58 intentional skips**,
**1,805 frontend passes**, **1 API-client pass**, and **146 direct and 146
aggregate browser passes, with no flaky case reported in either phase**.
The separate configured zero-retry groups report **20 / 9 / 5 / 10** passes.
These are source-bound job/log observations; independent validation of every
uploaded archive and physical-device acceptance are not implied.

The [PR candidate CI45540359069](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45540359069)
was successful at workflow level but reported **145 passed plus one flaky case**
in both direct and aggregate browser phases. Preserve direct artifact
`14989968065` and aggregate artifact `14991575953`. In
`source-completion-new-work.spec.ts:27`, the login-body read at line 158 failed
with `Network.getResponseBody`; retry 1 passed. The unchanged older main
[CI44997636297](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44997636297)
direct phase has the same observed failure and flaky classification. This
corrects any inference that the earlier **145 passes** summary meant no flakes.

The fresh-main pass does **not** establish the underlying cause or fix the known
intermittent response-body failure. Its investigation remains open. No workflow
rerun, retry increase, test quarantine or weakened assertion is part of this
reconciliation. The next engineering task is a bounded reproduction and source
investigation of that failure, preserving independent authentication and reception
readback semantics before accepting any proposed correction.

V0.1 remains **partial**. The inventory implementation, FR-INV-001–012 gaps,
G1–G6, T1–T8, R01-T035, real stock counts, installation-specific restore and
operational deployment boundaries above remain unchanged. Historical failed
receipts remain failed; successful postmerge CI does not waive these gates.

The next bounded test correction and native evidence are recorded in the
[November 26 destination-document checkpoint](2026-11-26-source-completion-login-document.md).
It preserves this postmerge receipt and does not revise historical failures.
