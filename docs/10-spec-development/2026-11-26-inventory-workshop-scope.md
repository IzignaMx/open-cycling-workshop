# Keep inventory selection aligned with its workshop scope · 2026-11-26

## Source and requirements

This local candidate starts from `a66c581c567a39a3971148e5abfae89d9aa96366`,
the exact [PR126](https://github.com/IzignaMx/open-cycling-workshop/pull/126)
inventory-page retry candidate. PR126 is still draft and its main CI is running
at this authored checkpoint; five companion workflows have passed. It has not
been integrated into main. Its [local retry evidence](2026-11-26-inventory-page-retry.md)
does not qualify this later source, and neither candidate inherits acceptance
from an earlier main or a successful retry.

The accepted [connected inventory read ADR, R1](../02-technical-architecture/2026-10-15-connected-inventory-read.md#generic-connected-read-capture-owned-by-the-runtime-r1)
already distinguishes the current operational workshop from an account-only
choice in the current bounded authorized directory. Account-only reads use
context metadata without an operational kernel, baseline or offline admission.
R3 preserves current scope, separate request generations and synchronous
invalidation of obsolete readings. INV-R07/INV-R08 retain the corresponding
lifecycle and presentation checks.

This increment applies those existing rules. FR-IAM-004/008, SEC-002 and the
[UX principles](../04-ux-design/open-cycling-workshop-platform-phase-4-ux-ui-design-system-v0.1.md#ux-principles)
UX-01, UX-04, UX-05 and UX-10 support clear scope, eligible controls and visible
recovery. No normative ADR or product requirement is changed.

## Reproduced mismatch and bounded correction

Two isolated source regressions fail on the baseline:

- An account-only reader can retain Product A and its admitted location context
  after the runtime replaces the directory page with a page containing another
  location. The select control becomes empty while the earlier inventory remains.
- An organization-wide account with an active operational workshop sees inventory
  directory selection controls, although the actual runtime's `loadLocations`
  makes no request in that mode and inventory cannot select another operational
  workshop through this control.

The candidate's invariant is that the visible choice and displayed
inventory agree with the current permitted read mode. Directory controls belong
only to eligible account-only selection. Navigating that directory must invalidate
the old inventory selection and readings before another selection is admitted;
obsolete success or failure must not restore them. An operational reader continues
to use its actual selected workshop. The existing runtime remains the authority
for all context capture and directory requests.

The controller derives directory eligibility once from the runtime phase and
the current connected account's literal `locations.read` grant, without expanding
wildcards. A volatile directory revision binds the select value to the current
directory publication. Inventory-owned directory requests clear the previous
choice, catalog, stock, history and receipt state before dispatch; a shared
directory page replacement from the central workshop selector does the same
as it is published. Pending entries and late reads are invalidated by the
existing entry/currentness fences. While an inventory-owned directory read is
pending, selection and directory/verification actions are disabled and the
controller refuses duplicate loads or entries. Only the current completion can
unlock these actions; a replaced session, scope or request cannot unlock a
newer one. The operational reader instead sees an explicit scope explanation.

This is a presentation/current-read consistency correction. It is not evidence
of cross-tenant access, a new grant or a server authorization bypass. API shapes,
ledger calculations, writes, queues, offline behavior and operational workshop
selection remain outside the change. The recently added manual page retries and
their no-automatic-retry rule remain intact.

## Source and local verification

Focused source checks produced **eight expected failures and 20 passing controls**;
the separate actual-runtime composition produced **two expected failures**. A native
baseline run against the pinned `a66c581` PWA and disposable PostgreSQL **18.4**
also failed, with **one worker and zero retries** (15.1457 seconds). The fixture
contains **51 workshops**. After the central selector's **Más talleres**, the select
shows the new directory page and an empty value, but **Cantidad disponible**
remains present (expected zero matching elements, received one, test line 249).
The report is retained at
`apps/web/test-results/inventory-scope-red-20261126-report.json`.
The frozen baseline distribution is byte-identical to the PR126 local build
receipt. The fixture guard passes **4/4**.

The first native candidate recovered the directory journey (**1/1**, 5.6s,
zero retries), but a second controlled test held a real inventory-owned directory
request before dispatch: the selector was still enabled and the test failed
as expected (**1 failure**, 15.8525s, worker 1, retry 0). The loading-state
correction includes a focused RED for duplicate loading and a separate RED for
an entry attempted during that request (two verification calls rather than one).
The final controller and panel retain those guards and use the same runtime
authority. The isolated real-runtime composition became GREEN (2/2), and
the final inventory plus connected-read focused suite passed **137/137** with
no failures or skips. Independent source review found no blocking issue.
The complete frontend core suite on pinned Node 22.16.0 passed **1,828/1,828**
with no failures/skips (35.923s test phase). The pinned production PWA build passed.
The final native Chromium inventory suite passed **17/17** (53.0826s, worker 1,
retry 0, flaky 0, skip 0) against the rebuilt production PWA and actual local
PostgreSQL 18.4. The directory journey checks replacement by the central selector,
inventory-owned paging with a held actual request, removal of catalog and stock
while waiting, controls blocked until the new page arrives, selection/recovery,
and the operational owner's current-workshop read without directory controls.
It checks a 320px panel and 44px control targets. All previous inventory journeys,
including privacy, four themes, manual retries, and access invalidation, remain.
The fixture still uses synthetic locations, products and quantities; no workshop
data is accessed. The safe local receipt
`artifacts/inventory-scope-20261126/native-local-receipt.json` has SHA-256
`387dc2da3822139345c473c62a44dfa460df3dfd3d1ca572cea33ffb4e1a8b1e`.
It binds source and build hashes unchanged through execution, the baseline and
intermediate reports, and the confirmed absence of the disposable PostgreSQL
container after cleanup. E2E TypeScript, touched ESLint, Ruff lint/format,
Prettier and diff validation passed. Repository contracts passed **227/227**
and the repository verifier returned OK. Exact hosted qualification remains
pending; the scope branch is a successor of the still-unmerged PR126 candidate,
not a fresh-main verification or deployment.

A preflight invocation of the global V0.1 verifier on the base used the default
unpinned Python/Node/pnpm environment and failed missing-dependency and archived
package-manager-pin checks; the receipt is retained at
`artifacts/local-qualification-unpinned-preflight-20261126.json`. Rechecking the
runtime HTTP smoke, OpenAPI contract and repository contracts with Python 3.13.5
and the environment's installed dependencies passed on the base. The later scoped
verification above uses pinned Node/pnpm and the guarded PostgreSQL fixture. We do
not claim that the aggregate V0.1 verifier or physical qualification passed.

## Separate branding investigation

A separate isolated probe investigated the
same baseline source independently of this inventory change. Its `source.json`
and `receipt.json` record six production/test source hashes checked unchanged
after execution. Node **22.16.0**, fake IndexedDB and the actual compiled runtime,
kernel and branding cache were used; no native browser or PostgreSQL ran for
this probe.
The local safe receipt is `artifacts/inventory-scope-20261126/branding-probe/receipt.json`
(SHA-256 `9d3ca3925181bb12978c8d6693dcff8383868e8e172e0f429b1ad1b16feaf95d`);
the isolated reproducibility note and source hashes are retained alongside it.

Controlled scheduling lets initial sync advance trusted observation time during
the first cache write, then lets one genuine `checkLease`, `verifyAccount` or
customer refresh advance it during the single trailing write. Both writes are
legitimately refused by the unchanged immutable-entry-time fence. The runtime
settles operationally ready with no accepted profile and no branding message.
The existing explicit shared-brand refresh then succeeds in each scenario,
without changing the operational journal. Three final assertions expecting an
automatically published identity deliberately fail; the two existing initial-sync
controls pass. The RED probes remain RED.

This demonstrates the bounded-publication limitation already described in the
[connected branding correction](2026-10-15-connected-branding-refresh.md#bounded-lifecycle-correction).
It does **not** establish which event caused the historical administration CI
timeout, and this inventory increment does not fix that timeout. A possible
separate improvement is a generic unconfirmed-branding notice pointing to the
existing manual action when the current source has no accepted profile. Such
work needs its own regression and review; it must not publish refused content,
misclassify every refusal as an I/O failure, relax admission fences or introduce
an automatic retry loop.

## Retained limits

V0.1 remains **partial**. The [inventory requirements matrix](2026-11-25-project-inventory-audit.md#inventory-requirements-retained)
retains all FR-INV-001–012 gaps; no physical stock census or real workshop database
is inspected. T1–T8/R01-T035, physical assistive technology, G1–G6, actual
installation restore, quote activation/capacity and deployment remain distinct
open gates. Neither the isolated probe nor this synthetic inventory correction
qualifies a production installation or advances those gates.

## PR127 stacked evidence and retarget to main · 2026-11-26

[PR126 merged](2026-11-26-inventory-page-retry.md#pr126-scoped-acceptance-and-merge--2026-11-26)
as `5ccb44fef975cab7cf99af8bd5d5a72f4c1d017c`. This supersedes the earlier
authored statement that the base was draft/unmerged; the original local base
and evidence remain unchanged. Its fresh-main CI is separate and in progress.

[PR127](https://github.com/IzignaMx/open-cycling-workshop/pull/127) head
`479f4308520d3663d78cf30c20684813e67a6712` passed its stacked
[CI45905913295](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45905913295)
and all five companion workflows while based on PR126's branch at `a66c581`.
The tested synthetic merge is `68f4cc6efe970d00d228bc8da54420d19402950d`,
with tree `069a1dde5919dc560dacedbf6dd97150c2558a7b`, identical to the head tree.
Reviewed logs report **1,828 frontend passes**, **1 API-client pass** and
**6,813 Python passes / 58 intentional skips**.

Independent review of Python artifact `15157784964`, SHA-256
`44ee68a0251f761692a3689239c9408bc9f6cc9d9da6dce98a17ade5da6e7172`,
confirms the two shard receipts bind
the clean source, tested merge and tree, report **4,412 / 11** and **2,401 / 47**
passed/intentional-skipped cases respectively, with no failed, error, unrun or
unexpected-skipped cases, and confirm both owned-database cleanups absent.

Direct browser artifact `15159602188`, SHA-256
`604e118a7f379a6ac4668a7b07001d14cb0713e3d6faae66addf6c967fb52d67`,
and aggregate artifact `15159809434`, SHA-256
`b6c5d6d488ea53618cbbc81dc6060a4df818e68e76acd7d40dbceecc89ffefa4`,
were independently reviewed. Both contain **17 inventory cases**, each passing
once with retry zero and no errors. The directory journey's 107 steps verify
the four disabled controls, cleared readings and geometry; all four theme
journeys remain. The aggregate full browser phase passes **146 cases**, with
zero flaky or skipped cases. Direct reports **145 passed plus one flaky
source-completion case**: login response JSON fails through CDP
`Network.getResponseBody` and retry 1 passes. Its cause remains unproven; this
is not attributed to administration branding or fixed by the inventory change.
The failed safe observation again records zero main-frame navigations, empty
session checked, response seen/not from the service worker, body not validated
and login not completed. It does not establish why CDP could not return the body.
There is no global retry-free claim.

PR127 is now retargeted to `main` at `5ccb44f`. A clean local merge-tree check
for that base and the unchanged `479f430` head produces the same
`069a1dde5919dc560dacedbf6dd97150c2558a7b` tree. This establishes source
compatibility, not a new CI execution. The documentation reconciliation creates
a later candidate that requires its own exact retargeted CI and review before
merge. These stacked receipts do not prequalify that later commit. The current
checkpoint remains partial; no production or physical gate is promoted.

## PR127 retargeted acceptance and merge · 2026-11-27

The retargeted documentation candidate
`996f0bb5d55ef5788f557691e3b46169e5dd3778`, based on main
`5ccb44fef975cab7cf99af8bd5d5a72f4c1d017c`, was tested as synthetic merge
`812cc957e9d096d683437718bb86a83df5a670c2`. Candidate, tested merge and merged
main `971bdd20e14508b5335189b1eb56c4d93ef70cea` share tree
`778accf50baa41221da253e1bbf0881886cdda57`.
[CI45912843815](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45912843815)
and all five companion workflows succeeded. Reviewed logs report **6,813 Python
passes / 58 intentional skips**, cleanup, **1,828 frontend passes**,
**1 API-client pass**, and repeat groups **20 / 9 / 5 / 10**.

Independent actual ZIP/report review covered direct artifact `15162082559`,
SHA-256 `b061e32161c3081022be7449e17cbfc4450a0b8d696f1f4d43f930d76cd50b30`,
and aggregate artifact `15163246640`, SHA-256
`8cfd07471da3c973508597919cad4e3145e2f242c95c45227b86a72cdfd544ac`.
Both report **146 passing cases on their first attempt**, including **17/17
inventory cases**, with zero flaky, skipped or error cases. This exact retargeted
receipt supersedes the earlier pending qualification of `996f0bb`, without
reclassifying the older stacked candidate's source-completion failure.

PR127 is merged. Fresh-main [CI45918169386](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45918169386),
Local runtime `45918169473`, Security `45918169443`, quote microfixture
`45918169517` and presentation preview `45918169384` have started and are in
progress at this observation. Candidate acceptance does not qualify those runs.
PR128 has been retargeted to this new main; its original stacked evidence and
later documentation successor require separate source-bound reconciliation.
No clean browser run establishes the CDP cause or closes physical, recovery,
installation or deployment gates.

## Exact PR127 main outcome observed · 2026-11-27

Fresh-main [CI45918169386](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45918169386)
completed on `971bdd20e14508b5335189b1eb56c4d93ef70cea`, tree
`778accf50baa41221da253e1bbf0881886cdda57`, attempt 1. Both CI jobs and every
step succeeded; the four companion workflows listed above also succeeded on
that exact main. Logs report **6,813 Python passes / 58 intentional skips**,
zero unrun cases and verified shard cleanup, **1,828 frontend passes**,
**1 API-client pass**, and repeat groups **20 / 9 / 5 / 10**. Python counts and
cleanup here are log evidence; a new Python-archive review is not claimed.

Independent full-ZIP/report review covered direct artifact `15164467503`,
SHA-256 `f9f5653b6b5c7a7b94d94903b9f8d409d5c771ef1373b8fabf9e5344626b725b`,
and aggregate artifact `15165455270`, SHA-256
`d24fd0f3eb412a666a2f7acc3e6eb7eaf92c8761a05a31d2d101a91986de3ab4`.
Both native reports identify this exact main/run and one worker. Inventory
passes **17/17** and source-completion **1/1**, each at retry zero in both phases.
The aggregate passes **146/146**, without flakes, skips or errors.

Direct instead reports **145 passed plus one flaky administration case**.
At `administration.spec.ts:632`, `expectWorkshopIdentity` in
`helpers/workshop-identity.mjs:11` expected `["Taller administración A"]` but
received `["OCWP"]` until the existing **10,000 ms** predicate timeout.
Attempt 0 failed after **10,583 ms**; retry 1 passed after **16,808 ms**.
This is another observation of the unresolved identity fallback, not evidence
of its cause or a new fix. Direct is not classified as retry-free.

This receipt supersedes only the earlier PR127 fresh-main-pending statement.
It preserves the candidate's separate clean result, older CDP failures and the
new main administration failure. PR128 and branding recovery require their own
source-bound receipts; physical, installation, inventory-completion, recovery
and deployment gates remain open.
