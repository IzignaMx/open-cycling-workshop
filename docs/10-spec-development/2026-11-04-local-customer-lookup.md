# Local customer-name lookup: bounded design and implementation plan

## Product value and admission

S2 is an independently admitted local-read prerequisite for operating the already
shipped intake picker. It contributes partially to FR-CUS-002/R02-T001; the canonical
task depends on V0.1 and is not complete. Master Loop permits this documented
prerequisite without claiming V0.1 physical acceptance or opening general V0.2 work.

Today the intake select receives only the currently displayed ID-paginated customer
page. The useful outcome is finding and explicitly selecting an admitted local
customer beyond that first page while offline, without losing the intake draft.
A visible-page filter alone would not deliver that outcome.

## Exact bounded architecture

- `runtime/customer-lookup.ts` owns volatile query, query revision, cursor, pages
  examined, current result page and at most one selected customer pin. Only one
  lookup may be in flight; query edits invalidate old work without starting I/O.
- Search uses simple case-insensitive name substring matching, with a query limit
  of 200 Unicode code points. It does not normalize stored names or search contact
  fields, IDs or tags. Full IDs may identify duplicate-name options, not enable ID search.
- Each explicit search, continuation or restart reads one existing kernel page
  of at most 50 candidate IDs. Use the returned cursor even with zero matches;
  never advance from the last matching ID. Replace the displayed page rather than
  accumulating matches. Report pages examined, not a fabricated candidate count.
- A selected-record refresh may add one existing `readEntity` lookup. Thus 50 is
  a candidate-page bound, not 50 total DB reads or a latency guarantee: projection
  reconstruction may inspect retained history/dependencies. No capacity claim.
- The controller binds exact active source, capture source, view token and query
  generation before publishing. Non-ready state or missing customers.read masks
  and clears lookup data. Late results cannot reappear in another authorization
  context. Repository `selectedCustomer` uses existing authorized entity projection.
- The select shows the current browse OR search page plus one deduplicated,
  currently authorized pin: at most 51 options, no automatic first selection.
  Customer identity remains the full ID even when names collide. Changing query
  or pages must not rewrite the selected ID or other capture fields.
- Ready/restored selection is checked through current grants; a persisted draft ID
  is not authority to display a cached customer label. Preserve the draft when a
  label is unavailable. Query/results/pin are not persisted as new data.
- Search/continue/restart controls are type=button. Enter in the query must not
  submit the order. Existing explicit order submission, capability, identity and
  dependency checks remain unchanged.

## Honest completeness and exclusions

There is no global snapshot. Concurrent admitted changes can occur between page
reads; restart begins a new traversal. An available cursor means more local records
remain to examine, even if the current page has zero matches. Exhaustion describes
this local traversal, not all server customers or an immutable search result set.
Offer explicit continuation and restart; do not perform a full background scan.

Use only current admitted cache/owned-journal projections through existing kernel
queries. The legacy customers name index is not an authorization shortcut.
No schema, index, server API, new storage, query telemetry, credential or persistent
access change is admitted. Contact/email/phone/ID/tags search, global ranking,
accent-insensitive semantics and server-wide completeness remain deferred.

## Tests-first plan and stopping boundary

1. Capture behavioral RED: a matching customer after the first page is unavailable
   through existing intake lookup; exercise explicit traversal with a zero-match
   page and the actual kernel cursor, not a mocked complete search.
2. Implement the volatile owner and existing repository projection adapter. Prove
   fixed per-action page work, one in-flight request, page replacement, stale-query
   rejection and auth/scope/generation fencing with current runtime paths.
3. Integrate the picker and explicit stable-ID selection, duplicate names, bounded
   authorized pin, query Enter behavior and unchanged capture-draft lifecycle.
4. Verify offline continuation, scoped/optimistic projections and logout/revocation
   refusal through meaningful native tests. Collection/simulation alone does not
   establish native browser acceptance. Run full local suites and independent review.
5. Stop this local work at the reviewed package. Publication and hosted execution
   remain pending coordinator confirmation of applicable user authorization; local
   test results alone grant neither. No seventh M2 run, migration or new authority
   is granted.

## Current source stage: test-locator repair after diagnostic failure

[CI 41847937571](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41847937571)
on head `ab1c8947448536dcc7588ef0c3892990dd948b2c`, tested merge
`7f70e6fb092812e969096474f9b1f6bc99180ead`, tree
`7e5b2b391438c10c33a640cd56a0c841876a3ad7`, failed with 26/27 controls.
Direct and aggregate browser suites each reported 132 passed / 1 failed, with
one retry for the lookup case. Python: 6,127 passed + 58 exact expected skips;
frontend: 1,296 passed. Offline typechecking and the former broad-button locator
no longer failed. Runtime/security/micro evidence was accepted independently.
None of those partial results qualifies the package for merge. The 26/27 figure
covers aggregate controls, not every required workflow gate: direct browser failure
skipped sync/order, cutover, administration and inventory-expiry repetitions.
The always-run expiry guard invoked `check "skipped"` and failed closed; its
size/digest-verified artifact contains only `{"status":"incomplete"}`. Zero of
the ten required expiry repetitions ran. This is missing downstream qualification,
not evidence of an independently failing expiry scenario. All repetition gates
remain required for fresh acceptance.

Eight bounded diagnostic snapshots were validated from the terminal log. Page two
was READY, with exact 51-record baseline membership, the target admitted and its
name matching, the query matching, two pages examined and traversal exhausted.
The target option was present among two options, while selection remained empty.
The test nevertheless reported its descendant option locator absent at line 120.

Local diagnosis then rendered the actual OrderQuickIntake and Button with
ReactDOMServer, parsed the actual wrapping label tree, and exercised the verbatim
installed Playwright 1.62.0 getElementLabels, elementText and createTextMatcher
functions. The proof reports actualRenderedTargetOptionCount=1 and
exactClienteLabelMatches=0: exact label matching includes option text inside the
wrapping label, rather than using the control's accessible role name. The earlier
zero-count assertion was vacuous because the parent label locator matched nothing.
This demonstrates a test-locator defect, not a production pagination defect.
The proof is not native browser execution; native selection and the rest of the
scenario still require fresh hosted qualification.

The bounded repair changes only the test's customer-control locator to the named
combobox and asserts a positive count of one before descendant assertions. There
is no production lookup fix, broader search scope, new storage or authority.
Proof: `artifacts/customer-lookup/pr89-locator-repair/engine-proof.log` and retained
rendered HTML/script. Final frontend: 1,296 passed. Final full Python: 5,515 passed,
671 environment skips, 12 warnings, 383.52 s, exit 0, retained in
`artifacts/customer-lookup/pr89-locator-repair/full-python.log`. Product/test source
was frozen before that run; the final documentation and correction-contract stamp
followed. Post-stamp repository verification: 186 passed, binding those final
contract assertions separately. Documentation Ruff/format, Prettier and diff checks
passed. Strict web/offline/native typechecks and native collection passed, but no
native browser was executed locally. The repair changes five paths, 19 overall
against accepted main. These local results do not close hosted repetition gates.
Publication is not performed by this source checkpoint; merge remains blocked
until complete fresh qualification. No M2 execution is authorized.

Second failed receipt:
`artifacts/customer-lookup/pr89-diagnostic-qualification/final/review-corrected.json`, SHA256
`e63da20a411cf2371b29610712634ebc618ab534c6fd9d39c06f8272bc761f77`.
This corrected receipt explicitly includes downstream skipped repetition gates;
its initial version remains `review.json` (also retained as `review-initial.json`), SHA256
`f208000e8b7d97401d74e970a6d3af71f1f80bd44e3d3ef5c86c75d22d3d68c2`.
The approximately 358 MB direct and aggregate browser archives were not downloaded
or byte/trace/screenshot reviewed. Receipt/proof paths identify retained coordinator
archive artifacts, not tracked/public repository files. Preserve both failed runs
and their historical UNKNOWN diagnosis below; later local proof does not rewrite
the earlier evidence or establish all remaining native assertions.

## Historical source stage: initial hosted failure and bounded diagnosis

[PR89](https://github.com/IzignaMx/open-cycling-workshop/pull/89) initial head
`90802550261d3a634423f0fb6dab0dcdd18a693d`, tested merge
`8424d35fc04d41ed1a0c3045d7c36c7eeada6594`, tree
`325427062580dfd5eedf5b2e1b3b371328e10cfe`, was **not accepted**.
[CI 41821564647](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41821564647)
passed 25/27 controls. Both direct and aggregate browser suites reported
131 passed / 2 failed; each failing case retried once. The browser step has no
continue-on-error setting; its terminal conclusion was failure. An earlier
intermediate step-status reading was erroneous and was corrected. No step badge
alone establishes suite acceptance.
Python independently qualified 6,126 passed plus 58 exact expected skips;
frontend reported 1,293 passed. These results do not cancel the failed controls.
Fresh terminal step review also confirms that this initial run skipped all four
repetition groups and its always-run expiry guard failed. No repetition pass is
claimed for either failed run; aggregate counts omit these additional gates.

- Offline typechecking rejected `preventDefault` on the retained keyboard-event
  shim. The ordinary web typecheck had passed. A narrow shim correction has local
  proof; fresh combined validation remains pending.
- The existing capture-visit test's broad button locator became a strict-mode
  violation after lookup controls were added. A submit-specific locator correction
  has local proof; this does not establish a native rerun outcome.
- The new lookup case timed out waiting for the target option after its first
  continuation. Its cause remains UNKNOWN. Local probes with 51 confirmed baseline
  records and mounted App real-button interactions passed; they do not explain or
  disprove the hosted failure. Logs do not contain the missing page's DOM, status
  or cursor. The large browser ZIPs were not downloaded, and their screenshots,
  error-context files and traces were not byte-reviewed.

The coordinator approved bounded synthetic native diagnostic instrumentation and
ordinary CI publication. This is not broader search scope, a new storage/API/auth
change or a M2 execution. Merge remains blocked until complete fresh qualification.
The repair package contains six frontend/test paths and these four documentation/
contract paths, ten changed paths relative to the initial candidate and 19 overall
relative to accepted main. It does not contain a production lookup-behavior fix.
The diagnostic uses synthetic fixtures and bounded closed fields: exact 51-record
baseline membership, target-name-match boolean, phase/status/page observations,
query-equality booleans and counts. It does not emit raw customer IDs or names.

Amended frontend: 1,296/1,296 passed, including three new diagnostic privacy/bounds
tests. Strict web, offline and native typechecks, lint and format passed. Seven
affected native cases were collected, not executed locally; the one new lookup
case still lacks native acceptance. Final full Python: 5,514 passed, 671 environment
skips, 12 warnings, 395.12 s, exit 0, retained in
`artifacts/customer-lookup/pr89-repair/full-python.log`. Product/test source was
frozen before that run; only this documentation stamp followed. Post-stamp
repository verification: 185 passed, recorded separately in
`artifacts/local-customer-lookup/docs-repair-final-repository.log`. Documentation
Ruff/format, Prettier and diff checks passed. These are local repair/diagnostic
readiness results, not a successful native or hosted lookup outcome. Historical
local counts below do not qualify this changed diagnostic package.

Retained failure receipt:
`artifacts/customer-lookup/pr89-qualification/final/review.json`, SHA256
`af2dd26e6832418aa66b40f1e4413a66a2d56960e2ae3df0db7011c40ee657a5`.
Sanitized log excerpts and source-bound failure metadata are retained alongside it
in the coordinator archive, not as tracked/public repository artifacts. Preserve
this initial failure even if a later source passes. Physical and historical gates
remain unchanged.

## Historical pre-publication local evidence

Implementation and independent local review are complete. An
independent actual-runtime baseline with 61 customers showed that the first 50
options omit the named target, while existing next-page refresh returns it among
11 records. The target is not globally unreachable: the gap is name lookup and
stable selection across shared-page replacement. The selected draft ID persists,
but its option disappears when the displayed customer page changes. Evidence:
`artifacts/customer-lookup-admission/first-page-red.mjs` and `first-page-red.log`.
The initial frontend run retained five fixture failures in
`artifacts/customer-lookup/full-frontend.log`. Corrections used actual admitted
IDs and waited for currently authorized pin availability; these fixture failures
are not five production regressions. The corrected run is retained separately.

Integration also reproduced a real branding race with two held digest completions.
The retained `artifacts/customer-lookup/branding-tracked-red.log` distinguishes
that behavioral RED/control from the earlier fixture failures. The narrow fix
signals resolved, source-current page/selection reads through the existing offline
activity hook. Its existing offline-only coalescer and authority boundaries stay
unchanged; there is no new branding storage, network policy or persistent access.
Independent review passed all 21 focused lookup cases and a mutation removing both
activity signals detected the regression. A separate selection epoch protects
same-ID pin resolution and ABA changes without introducing I/O on query typing.

Final frontend: 1,293/1,293 passed; 21 focused lookup cases passed. One native PWA
case was collected and typechecked, not executed locally. These results do not
establish native or hosted acceptance. Final full Python on the frozen product:
5,513 passed, 671 environment skips, 12 warnings, 389.21 s, exit 0, retained in
`artifacts/customer-lookup/full-python-final.log`. This final run supersedes the
preliminary run for product validation and preceded only this documentation stamp.
Skipped checks are not qualification. Scope remains 15 files.

Post-stamp repository contracts: 184 passed, recorded separately in
`artifacts/local-customer-lookup/docs-final-repository-green.log`. Static checks,
types and build passed; the existing chunk-size warning remains. Publication is
not performed or granted by this local checkpoint; the coordinator determines
applicable user authorization before any external action.
Documentation contracts have their own retained RED evidence under
`artifacts/local-customer-lookup/`; that is not product behavior proof.
Physical T1–T8/R01-T035, capacity, broader OFF-007, SPENT40927223929,
UNKNOWN41011497919 and Pages remain unchanged.

## Historical accepted baseline

Main `5f5c0e3eab6af6693016781184e387d442106af9`, tree
`a5ff0e33250206d8f6ea8dc66a9df3d0ad79481a`, equivalent local `0fff4f27`.
[CI 41810260574](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41810260574)
passed 27/27: Python: 6,123 + 58 exact skips; frontend: 1,272; API: 1;
browsers: 132 direct-log / 132 aggregate; repeats: 20/9/5/10; kernel: 14;
zero retries. Two inline-intake PWA cases, 75 invalid batch items with two valid
peers and 28 replay cases were verified. Runtime 41810260669, security 41810260514
and micro 41810260531 were accepted. No M2 ran on main push. Large browser archives
were not downloaded or byte/trace/screenshot reviewed.

Retained coordinator receipt:
`artifacts/intake-admissibility/pr88-postmerge/final/review.json`, SHA256
`ed97f1fc5ec0af44cf8a5a5dd90d4e8a6ca6742acdafa2d90b6adb94b34b3255`.
Receipt/log paths are coordinator archive artifacts, not tracked/public repository
files. Their results do not qualify changed lookup source. Earlier source-stage
pending gates remain historical and do not grant current publication permission.
