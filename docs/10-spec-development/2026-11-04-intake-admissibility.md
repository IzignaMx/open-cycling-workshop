# Existing intake admissibility: bounded integrity prerequisite

## Admission and stopping boundary

This repairs already shipped bicycle/order commands under FR-BIK-003/R02-T002
and FR-SVC-001/R02-T005. It is not R01-T030, a new workshop feature, or completion
of either canonical V0.2 task. Master Loop permits a documented prerequisite
outside the active release: preventing invalid existing intake from entering the
journal/server is the reason here. V0.1 remains partial until its physical gates.

No search, schema, migration, credential, persistent authority or financial flow
is admitted. Stop at a locally reviewed candidate; publication and hosted execution
need separate approval. No seventh M2 permit is granted.

## Observed defect and full bounded field matrix

The coordinator supplied four real-controller RED cases: invalid inline intake
admitted two journal commands, or invalid order-only intake admitted one, and
cleared the user's draft. Evidence is retained under
`artifacts/order-bicycle-admission/`. Pure builder/domain/schema observations also
show missing caps and Python whitespace differences; these are not native PostgreSQL
proof or an assertion of observed PostgreSQL data loss.

- **Bicycle brand/model/type/wheel/notes:** enforce existing database String caps
  of 120/120/60/30/2000 Unicode code points after existing normalization. Brand is
  required. Reject server-blank prepared brand, including Python whitespace that
  JavaScript preparation leaves intact. Preserve existing prepared values and
  each layer's normalization; no truncation or stored-command rewriting.
- **Bicycle nullable fields and types:** retain omission and explicit null behavior
  and normalized blank-to-null semantics. Reject malformed supplied types instead
  of stringifying required brand or silently clearing nullable fields. Create
  optional fields remain optional; update omission preserves existing values.
- **Order reported problem:** retain required-string/nonblank behavior and reject
  a prepared value that becomes blank under Python whitespace normalization.
  Do not impose its REST-only 4,000-character cap on the existing Text domain.
- **Intake condition/accessories:** nullable text retains omission/null/blank
  semantics and existing normalization. Reject malformed types without silently
  dropping data. Their REST-only 4,000/2,000 caps are excluded: DB columns are Text.
- **Priority:** enforce the existing String(30) limit. Omitted priority defaults to normal;
  supplied null/non-string priority rejects; the existing frontend blank-string
  default remains unchanged.
  Keep the existing priority UI allowlist; it was already guarded and is not a
  new RED claim. Do not invent a domain enum or reinterpret valid priority strings.
- **References and transition notes:** customer/bicycle IDs, authority, state
  transitions, actor binding, managed/financial orders and transition notes are
  outside this increment. Existing ownership/dependency checks remain binding.

Source anchors: `apps/web/src/features/bicycles/local-bicycle.ts`,
`features/orders/local-order.ts`, `runtime/repositories.ts`; backend
`cycling_workshop/bicycles/{domain,schemas,models}.py`,
`service_orders/{domain,schemas,models}.py` and `sync/service.py`.
REST raw validation remains unchanged. This is bounded admissibility, not a claim
that native inputs, local prepared values and backend normalization are identical.

## Atomicity, compatibility and verification plan

1. Retain behavioral RED through the real controller and corrected backend
   fixtures. Local invalid paired intake must admit no journal commands and no
   orphan bicycle or order, retain all editable input, and return closed errors.
2. Validate all scoped fields before local pair commit and backend entity effects.
   Preserve normalization, Unicode code-point counting, null/default/omission and
   create unknown-key compatibility. Do not widen identity or scope authority.
3. Keep receipt-first replay of already acknowledged commands. New invalid sync
   items conflict within existing per-item savepoints; valid peers still succeed.
   Do not promise a new server transaction spanning independently delivered items.
4. Verify no row/version/change effects on rejection, successful correction of
   retained draft, valid batch peers, historical replay and boundary values.
5. Run focused and full local suites, static checks and independent review. Author
   meaningful native cases separately; collection or simulations are not native
   qualification. Record final counts only after actual terminal evidence.

## Current checkpoint

Implementation and independent local review are complete. Exact local evidence:

- Full Python: 5,510 passed, 671 environment skips, 12 warnings, 395.46 s,
  exit 0 (`artifacts/intake-admissibility/full-python.log`). This completed before
  the final documentation-only stamp; skipped checks are not native qualification.
- Full frontend: 1,272 passed. Focused backend: 200 passed with one existing warning.
- Independent review accepted 200 backend, 33 builder/feedback and five actual
  recovery cases; five mutation controls were detected and exhaustive Unicode
  whitespace comparison matched. These are local evidence, not hosted acceptance.
- Repository: 181 passed, with a separate post-stamp rerun recorded in
  `artifacts/order-bicycle-admission/docs-final-repository-green.log`.
- Static checks, types and build passed; the existing chunk-size warning remains.
- Scope: 25 files. Two new native PWA cases were authored; 16 cases in the file
  were collected, zero executed locally. Native browser/PostgreSQL and hosted
  qualification remain pending for this candidate.
- No publication or new execution authority follows from these local results.

Optional bicycle omission remains supported: no inline bicycle request must not
be reinterpreted as a required-brand error. When paired input is present, local
admission is all-or-nothing; server delivery retains per-item savepoints rather
than promising cross-item atomicity. REST-only Text caps and transition notes
remain excluded. No normalization, IDs or authority expansion. Rejecting supplied null priority
is an intentional correction of prior silent coercion, not preserved behavior.

Physical T1–T8/R01-T035, capacity, broader OFF-007, SPENT40927223929,
UNKNOWN41011497919 and Pages remain unchanged.

## Historical accepted baseline, not candidate evidence

Main `2f9abe5c8e74887177882032c8ba474f6e9bf761`, tree
`a64e063d9ae91c36b53286d9e62e9f8b73b9af29`, equivalent local `14d4c25d`.
[CI 41793841607](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41793841607)
passed 27/27: Python: 6,045 + 58 exact skips; frontend: 1,256; API: 1;
browsers: 130 direct-log / 130 aggregate; repeats: 20/9/5/10; kernel: 14;
zero retries. The single-label email PWA, typed-field batch and 12 historical
receipt-replay cases were verified. Runtime 41793841605, security 41793841620
and micro 41793841622 were accepted. No M2 workflow ran on this main push.
Large browser ZIPs were not downloaded or byte/trace/screenshot reviewed.

Retained coordinator receipt:
`artifacts/customer-admissibility/pr87-postmerge/final/review.json`, SHA256
`1595e284d9c1079647b636ede9c4b48b9d9c9ec3640a4a7904512cc8f730f43b`.
This and the local RED artifacts are not tracked/public repository files; they
are available through the coordinator archive. Prior source-stage pending gates
remain historical, not a request to repeat consumed work or current permission.
