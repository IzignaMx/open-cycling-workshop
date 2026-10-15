# V0.2 Increment 2 · Task 5 · Pure quote decision domain

## Delivered boundary and traceability

Based on main41 `88ee267f2d9fa1e63836ca5c9a47e49f21882fd6`, this implements the
reviewed pure-domain part of Task 5. FR-SVC-005/007/008/009/016 and BR-004/005/006/007
bind decisions to exact immutable revisions; NFR-009 and the accepted arithmetic
contract preserve currency and integer minor units. OFF-005/008/009/012 and
SEC-002/003 constrain future integration, rather than being newly delivered here.
The [decision ADR](../02-technical-architecture/2026-10-15-quote-decisions-and-partial-pricing.md)
records source references, alternatives and the sixteen-row risk/test matrix.
The reviewed proposal's SHA-256 was
`28fc49f90012a0261adc026fa3b3c7276cfef508c2f012c5ad0eff4096bc44b4`.

- `quotes/history.py` validates the complete supplied revision chain, using its
  root revision ID as lineage identity. It rejects gaps, reused revision IDs,
  altered line kinds/products and resurrected retired line IDs. Existing
  `Quote.quote_id` semantics and standalone revision behavior are preserved.
- `quotes/decisions.py` records typed, frozen approval/rejection/partial evidence,
  exact scope/revision/selection, canonical command proof, one recording actor/time
  and computed pricing. Current-revision replacements and withdrawals append;
  superseded-revision edits are explicitly deferred. Previous receipts remain
  immutable and exact retries return them alongside the current projection.
- Selected whole labor/part lines retain their original full-quote discount
  allocations. Each tax is rounded once on its selected discounted base. A shared
  private allocation helper preserves Task 4's results, lexical remainder ties
  and refusal behavior. Price, quantity or commercial-term edits require revision.
- Revision and decision sequences are distinct optimistic preconditions. Revision
  creation cannot precede the latest recorded evidence; reconstructed entries
  must belong to their observed revision interval. Equal timestamps use explicit
  version/sequence ordering, never last-writer-wins.
- A pure initial-transition planner requires a current supplied ledger, its latest
  applicable initial receipt, matching order scope/version and `DIAGNOSIS`.
  Replay, replacement, withdrawal and retained pre-revision results cannot plan a
  transition. The plan carries preconditions; it does not execute an order action.
- New decisions produce an in-memory event intent with an internal evidence ID,
  without raw notes, source references or correction reasons. It is not a durable
  order timeline or outbox record. Replays and revisions create no decision event.

## Test-first and independent evidence

Behavioral source was reviewed at `adb4ea9f8e72c6cb556b46886524740688628fa3`.
A subsequent package-docstring clarification changes no behavior. The original
106 Task 4 tests are byte-identical to the baseline; their SHA-256 remains
`9cfd15463385437f50635a4a38ff6aab0f126dc714e93e316afadbf59c09c7cc`.

1. Missing-feature RED: the new history/decision suites failed collection before
   the production modules existed; independent subset-pricing tests also observed
   missing-module RED. Initial focused GREEN was 171 quote cases.
2. Hardening RED: six cases exposed boolean/float pricing lookalikes, a nonboolean
   per-line flag and a mismatched planner event. After correction and expanded
   cases, the quote suite reached 239 passes.
3. Independent source review reproduced a mutable `UserString` enum token that
   changed a retained approval into rejection. Four committed rejection cases
   failed before exact-string guards were added for mode, outcome, party kind and
   channel. Corrective GREEN: **243 quote tests**, zero failures/skips, consisting
   of 106 original arithmetic, 17 history, 77 decision and 43 pricing cases.
4. Independent review reran those 243 tests and the combined quote/order/inventory
   domain suite: **282 passed**. Focused Ruff and format passed (8 files); strict
   mypy passed (4 quote source files). No blocking source finding remains.
5. Committed independent pricing properties cover 180 seeded overlapping-discount
   cases and 1,440 permutations, exact values above 2^53, lexical ties, overlapping
   scopes, zero gross, empty/full subsets and tax rounding boundaries. They use a
   rational oracle distinct from the production helper.
6. Additional reviewer-only evidence: 2,000 generated quotes, of which 877 valid
   candidates exactly matched baseline full totals/line amounts and 1,123 had the
   same refusal type/message. All 21,116 subsets of valid candidates matched an
   independent Fraction oracle. Nine correction chains passed 36 receipt/current-
   projection/stale-planner assertions; 41 further adversarial checks passed.
   These review probes are separate from the 243 committed test count.

The independent review report's SHA-256 is
`1b35e30d5408baba9bef6de6d9129623fdbc68913a9f1ea09f322beab7003d72`.
It retains the initial defect and its independent closure; local review artifacts
and reproducible probes accompany the coordinator's handoff. Source review does
not establish a durable workflow, actor/customer authenticity or concurrency.

### Risk-to-test map

- QD-01/02: `test_quote_history.py` covers complete chains and stable line identity.
- QD-03/08/09/10/16: decision tests cover canonical proof, changed-ID conflicts,
  exact replay, current projection, correction chains and forged reconstruction.
- QD-04/05/06/14: pricing tests cover original allocation, independent tax rounding,
  precision and canonical immutable outputs; all original arithmetic tests remain.
- QD-07/11/12: decision tests cover chronology, superseded-edit refusal, retained
  stale results, mismatched events and every non-DIAGNOSIS order state.
- QD-13/15: combined unchanged order/inventory domain tests and source-scope review
  confirm no operational mutation or persistence/API/schema/sync/UI dependency.

## Repository qualification

The first aggregate attempt lost its executor transport before any result was
persisted. Its empty log is **unverified**, not a passing run. The next completed
run, on reviewed behavioral source `adb4ea9`, failed: 19 checks passed, two failed,
five were blocked. Python reported 31 failures, 2,261 passes, 224 skips and 10
errors; full mypy lacked PIL. That run used a stale pre-remediation interpreter
without Pillow and with PyJWT 2.13.0, Starlette 0.52.1 and FastAPI 0.128.8. The
failed result is retained; it is not evidence against or qualification of the
changed domain by itself.

The unchanged lock specifies Pillow 12.3.0, PyJWT 2.15.1, Starlette 1.3.1 and
FastAPI 0.133.1. A verified matching existing environment is now used read-only,
with imports bound to this checkout. All installed Linux registry packages match
the lock; Windows-only colorama/tzdata are absent. No lock/dependency or other
worktree change was needed. Quote plus existing dependency-security tests passed
257/257 on that environment. The locked-source aggregate subsequently completed
on Python 3.13.5 / Node 22.16.0: **21 checks passed, zero failures, five explicit
blockers**. Full Python: **2,302 passed, 224 skipped, three warnings**. Frontend:
**773 passed**, zero failures/skips. Full mypy: **101 source files**, no issues.
Ruff/format, frontend lint/format/typechecks, repository/OpenAPI/client contracts,
real SQLite HTTP smoke, API-client tests and current/pinned-old PWA builds passed.
A transient executor transport interruption did not erase the terminal JSON;
only that persisted completed result is counted.

The five blockers are absent PostgreSQL test URL, Docker CLI, PostgreSQL tools,
managed Chromium navigation restriction for the 100k IndexedDB benchmark and
absent destructive browser-E2E database URL. PostgreSQL-dependent skips remain
unqualified, and no browser-policy restriction was bypassed. This is a **partial**
local aggregate, not a full native/hosted qualification. Final clean-head artifact
identity and independent documentation review accompany the coordinator handoff.

Hosted exact-head CI/Security/DCO remain the coordinator's publication gates. No
remote publication is performed by this implementation worktree.

## Explicit limitations and next boundary

Task 5's durable application/timeline integration remains open. The module does
not authenticate evidence, authorize access, discover omitted concurrent history
or prevent a caller reusing an entire old detached snapshot. Future persistence
must obtain canonical data, authorize reads and retries, and revalidate quote,
order and decision preconditions under one transaction/serialization boundary.
An event intent or ID is not proof of customer intent or a permission grant.

There is no persistence, migration, API/DTO, capability/catalog change, sync entity,
local store, editor or other UI. Existing generic order transitions remain as
before; this increment does not claim live quote-aware enforcement. No stock is
reserved, released or consumed; reservation/consumption remain separately
explicit, online, authorized operations with their existing append-only ledger
semantics. No invoice, payment, POS or generic event-sourcing framework is added.

Historical superseded-evidence edits, quantity-level partial approval, changes to
prices within a decision, cumulative approval merging and operational reversal
of authorized work are deferred. A replacement is a complete new selection.
Withdrawal invalidates a record without claiming customer rejection.

Current inspected SQL head is branding `0011`; authenticated local schema is 7.
Future quote reservations are SQL `0012` / local 8, superseding old `0010` / local 6
notes. Reinspect actual heads before any persistence work; no empty reservation or
historical migration is added here. PostgreSQL races, native browser/offline,
restore/deployment, physical devices and manual accessibility keep their own
open gates. This sub-slice is not a complete money-and-parts journey or release.
