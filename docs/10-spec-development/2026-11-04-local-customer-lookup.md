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

## Current evidence

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
