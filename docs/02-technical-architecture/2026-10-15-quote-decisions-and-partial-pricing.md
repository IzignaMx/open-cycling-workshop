# ADR proposal · Quote identity, decision evidence and partial pricing

- Date: 2026-10-15
- Status: **Accepted for the bounded Task 5 pure-domain implementation**
- Baseline inspected: `88ee267f2d9fa1e63836ca5c9a47e49f21882fd6` (main41)
- Scope: V0.2 Increment 2 Task 5, pure Python domain only
- Requirements: FR-SVC-005/007/008/009/016, BR-004/005/006/007,
  OFF-005/008/009/012, SEC-002/003, NFR-009
- Related boundary, not delivered here: FR-SVC-011 and FR-PRT-003/004

## 1. Decision summary

Keep the existing `Quote.quote_id` as an **immutable revision ID**. Identify its
lineage by the root revision's ID, without renaming existing fields or changing
previous snapshots. Add an immutable, validated lineage/history wrapper and an
append-only customer-decision ledger. A decision binds the lineage, exact
revision ID and version, exact charge-line set, computed price breakdown and
recorded evidence. It never follows a line ID onto a newer quote automatically.

A partial approval selects whole, unchanged labor/part lines. It retains each
selected line's discount allocation from the complete original quote, and
recalculates each tax once on the selected discounted base with the existing
integer half-up rule. A price, quantity, rate, scope or commercial-condition
change requires a new quote revision and new evidence. It is not a decision
"override".

Decision corrections append a replacement or withdrawal linked to the prior
entry on the current revision; they do not overwrite history. Editing evidence
for superseded revisions is explicitly deferred; its immutable records and exact
historical replay remain available. Exact retries return the original result
without another event. A current quote revision and a decision-log sequence are
separate optimistic preconditions. Customer decisions, operational order states
and stock commands remain separate concepts.

The implementation stop is reviewed pure-domain code/tests and documentation.
No persistence, migration, HTTP route/DTO, capability/catalog change, sync
entity, local store, UI, deployment or actual customer action is included.

## 2. Why this decision is needed

The accepted arithmetic ADR already fixes integer money, rounding, original-gross
proportional discounts, lexical-ID remainder ties and immutable revisions [S2].
It does not define approval evidence or prices for an approved subset. The Task 5
plan says "lines subset with overrides" but cannot mean rewriting the revision
which BR-004/005 require the customer to authorize [S1, S3]. Here, that shorthand
means line decision selection; monetary overrides require a revision.

The current domain's `quote_id` changes on every revision. It has predecessor and
successor links, but no lineage field, historical line-ID check or decision
records [S4]. `QuoteTotals.line_amounts` contains gross charge values, negative
whole-discount values and tax values; it does **not** expose per-charge discount
allocations. Summing selected `line_amounts` would therefore be wrong.

The current order state machine allows `authorize` and `reject` only from
`DIAGNOSIS`. It has no `authorize_partial` action or quote-aware event payload
[S5]. The implementation must not invent a transition, write evidence into a
free-text note as if it were a durable association, or claim live enforcement.

## 3. Identity and immutable history

### 3.1 Revision identity versus lineage identity

1. `quote_id` continues to mean the exact revision record ID. `version` continues
   to mean its positive revision number within one lineage. Do not reuse it as
   an order version or a decision sequence.
2. A new `QuoteHistory` value has `lineage_id = revisions[0].quote_id` and an
   immutable tuple of all supplied revisions in version order. This avoids
   adding an inferred field to previously constructed `Quote` instances.
3. Validate the complete supplied chain: starts at version 1; contiguous
   versions; unique revision IDs across the entire history; one organization,
   location, order and currency; exact predecessor/successor pairs; predecessor
   `superseded_at` equals successor `created_at`; only the final revision has
   neither supersession field. Reject gaps, branches, cycles and reused IDs.
   Equal creation times are valid; versions establish order.
4. Appending a revision delegates arithmetic and predecessor marking to the
   existing `Quote.revise`, then validates the whole resulting history. Existing
   quote constructor/revise behavior remains compatible. Financial inputs,
   totals and creation timestamps never change. Only the returned predecessor's
   already-specified supersession metadata is replaced, not the input object.
5. A standalone later `Quote` cannot be adopted by guessing its root from the
   immediate predecessor, order ID or version. Supply the complete validated
   chain. Import/legacy repair and repository reconstruction are later work.
6. This wrapper proves consistency of the supplied in-memory snapshot only.
   It cannot discover an omitted concurrent successor. Future persistence must
   provide the canonical chain and enforce serialization/CAS in a transaction.

The pure layer follows the existing identifier rules (nonblank strings without
whitespace); generated synchronizable IDs use the existing UUIDv7 helper.
External UUIDv7 validation and bounded transport are later boundary work. An ID
is not authorization, a signature, a hash of content or proof of customer intent.

### 3.2 Stable line identities

A line's `line_id` is stable within the lineage when it still represents the
same logical item. Every evidence reference is `(quote_id, line_id)`, not a bare
line ID. A revision may change that line's price, description, quantity/minutes
or tax/discount parameters, but approvals never carry over.

- Reordering inputs keeps IDs. The calculator's lexical remainder rule stays
  unchanged.
- A retained ID must retain its line kind. A retained part line must retain its
  product ID. Replacing the product or converting labor to a part uses a new ID.
- Removing a line retires that ID for the lineage. A later reintroduction uses a
  new ID; it cannot resurrect an old approved identity.
- Tax/discount IDs obey the same no-kind-change and no-reuse rules. Their scopes
  can change only in a new revision and still reference that revision's charges.
- New histories with a kind/product switch or retired-ID reuse fail closed.
  No previous evidence or arbitrary history is silently repaired.

These additional cross-revision checks live at the new history boundary; they
must not silently change the accepted standalone Task 4 API.

## 4. Decisions and evidence

### 4.1 Immutable values

Proposed type names are implementation guidance, not a published wire contract:

- `QuoteHistory`: validated revisions and derived current head.
- `DecisionEvidence`: attested decision maker reference, channel and customer-
  decision time, plus optional source reference/note. It contains no recorder.
- `EntryRecording`: the single recording actor/time for each new entry, plus a
  mandatory reason for replacement/correction/withdrawal. A correction records
  the correcting actor and new recording time here; it does not duplicate or
  overwrite the prior entry's recording facts.
- `QuoteDecisionEntry`: identity/scope, target revision, decision sequence,
  outcome, complete per-charge decisions, customer evidence where applicable,
  computed pricing, one `EntryRecording` and any correction predecessor.
- `QuoteDecisionLedger`: history plus ordered immutable entries and canonical
  command proof sufficient to recognize exact replay.
- `QuoteDecisionResult`: current returned ledger, historical-or-new receipt
  entry, current `DecisionProjection`, and a new domain-event intent only for a
  newly appended entry. Exact replay returns `replayed = true`, the original
  receipt, the unchanged **current** ledger/projection and **no new event intent**;
  it never returns the old ledger snapshot as the current state.
- `DecisionProjection`: current revision, its latest entry, applicable approved
  charge IDs and approved totals, or an explicit no-current-approval reason.

All nested collections are copied to immutable canonical tuples. Reject unknown
outcomes/channels, malformed identities, duplicate selections and mixed scopes.
No constructor accepts caller-supplied totals as authoritative. Reconstructing a
ledger validates/recomputes its derived pricing from the referenced revision;
malformed supplied history is not silently accepted.

### 4.2 Outcome and per-line meaning

For the complete labor/part set `C` of one revision:

- `APPROVE`: approved set is all of `C`.
- `REJECT`: approved set is empty and every charge is declined.
- `PARTIAL`: approved set is a nonempty proper subset of `C`; every other charge
  is explicitly declined for this decision. Unknown, repeated, tax or discount
  IDs are invalid selections. Empty/all selections must use the corresponding
  explicit full action rather than being silently converted.
- `WITHDRAW`: an append-only correction of a previous entry; it leaves no
  applicable approval. It is neither customer rejection nor an order state.

Each charge has a canonical `APPROVED` or `DECLINED` record linked to the entry's
single evidence object. The result retains the approved and declined sets,
including zero-priced charges. A withdrawal has no new per-charge decision and
references the prior entry. There is no unresolved/implicitly approved charge.

One entry represents one attested decision with one maker/channel/time. Different
conversations cannot be combined into fabricated common evidence. A later
change to the selected set is a complete replacement decision with its own
fresh evidence, not an accumulated union of several partial approvals.

### 4.3 What the evidence does and does not establish

Separate `decision_maker` from `recorded_by_actor_id`. The former is an asserted
party reference (`customer` or `representative`, each with a nonblank party ID);
the latter is the workshop actor recording it. Do not infer customer identity
from the authenticated staff user or imply a staff note is a verified signature.
The future application validates the order/customer relationship and any
representative authority. The pure domain cannot authenticate either party.

Initial channels are `in_person`, `phone`, `email`, `messaging`, `written` and
`portal`. These classify evidence; accepting the `portal` enum does not implement
or certify a portal, token, external sender or signature-verification mechanism.
An adapter must establish the channel's actual provenance before recording it.
No communication is sent or inbox/document fetched by a decision operation.

Both `decided_at` and `EntryRecording.recorded_at` are aware timestamps normalized
to UTC. Each entry has exactly one recording actor/time. Corrected customer
facts appear in its new `DecisionEvidence`, while the prior entry retains its
original customer and recorder facts unchanged. A withdrawal has only recording
evidence, without a fabricated customer maker/channel/decision time.

The new aggregate uses these chronological invariants:

1. Customer decision time must be at or after target revision creation, at or
   before recording time, and, for a superseded revision, at or before its
   `superseded_at`. The active interval is inclusive at both ends; equal times
   are valid because revision versions and decision sequences establish order.
2. A new entry's recording time must be at or after the current head's creation
   and the preceding ledger entry's recording time. A replacement customer act
   also cannot precede the most recent customer-decision time in its replaced
   chain (skip withdrawal entries, which have no customer-decision time).
3. Aggregate revision creation must be at or after the latest decision/correction/
   withdrawal recording time, as well as the current head's creation. This
   prevents an accepted decision from being made to appear after supersession
   by subsequently backdating a revision. Standalone `Quote.revise` is unchanged.
4. Record correction/withdrawal targets only the current head. A current
   correction may change an earlier reported customer-decision time within that
   revision's active interval; its new recording time still follows rule 2.
   A correction to any superseded revision is refused even when its proposed
   customer time is within the old interval. Late recording/correction of such
   evidence is deferred, without deleting or altering the existing entry.
5. Reconstructing the aggregate enforces the same rules: each entry targeted its
   command's observed head at admission, and its recording time falls in that
   revision's inclusive active interval. Observed head versions never decrease
   across decision sequences. Equal-time boundaries do not allow a backward
   prefix or branch. Later supersession does not invalidate an entry that was
   legitimately recorded while its revision was current.

These are consistency rules, not proof of when an external customer actually
spoke. Recording a late customer act on an already superseded quote would need
a distinct historical-evidence policy and is outside this slice. The required
correction reason documents a correction; it does not bypass the interval.

Optional source references are opaque identifiers, never dereferenced by the
pure domain. Notes/reasons remain private evidence and are not automatically
copied to customer-visible events, logs or exceptions. The later DTO/storage
boundary must impose size, redaction and visibility rules. Never include secrets
or a portal bearer token as an evidence reference.

## 5. Approved-subset money contract

### 5.1 Preserve the complete revision's discount allocation

Let `g_i` be the original rounded gross amount for charge `i`. For each discount
`d`, compute `a_di` on its **complete original scope** exactly as Task 4 does:
original gross weights, integer floor shares, largest remainders, lexical line-ID
ties. `n_i = g_i - sum(a_di)` is that charge's original net amount.

For approved charge set `A`:

1. Approved subtotal is `sum(g_i for i in A)`.
2. For every original discount, retain only `a_di` for selected charges. Approved
   discount is `sum(a_di for i in A)`. Do not move declined lines' discount shares
   onto selected lines, re-run allocation on a narrowed scope, apply the entire
   original fixed discount, or compute a floating-point percentage of the total.
3. For every original tax `t`, intersect its original base with `A`. Compute
   `round_half_up(sum(n_i for i in intersection) * rate_bps / 10000)` once for
   that tax. An empty base yields zero. Do not retain a full-quote tax amount,
   allocate that rounded amount proportionally, or round tax per charge.
4. Approved total is approved subtotal minus approved discount plus the sum of
   those recomputed tax amounts. Currency is unchanged; all values are exact
   integer minor units. Full approval must equal **all** original monetary
   totals; rejection/withdrawal yields zero approved amounts.

Expose an immutable explanatory breakdown: selected charge gross/discount/net,
original discount IDs and their selected per-charge shares, original tax IDs,
selected tax bases and computed tax amounts. Keep zero amounts where needed to
show the original term's identity. There is no allocated "tax per charge" when
only a rounded tax-base total is mathematically defined.

Implementation should extract/reuse the original allocation calculation into
one private integer-only helper, with byte-for-byte equivalent Task 4 observable
results and its full test suite retained. A second divergent pricing algorithm
or adding a new required public `QuoteTotals` field is unnecessary.

### 5.2 Concrete oracle examples

- Two charges `a = 101`, `b = 100`; a fixed discount of `5` scoped to both; tax
  `1600` bps on both. Original discount allocations are `a = 3`, `b = 2`; nets
  `98, 98`; original tax `31`, total `227`. Approve only `b`: subtotal `100`,
  discount `2`, tax `16`, total `114`. The discount is neither `5` nor newly
  reallocated; the tax is not the original `31`.
- Charges `a = 1`, `b = 1`; discount `1`: the lexical tie gives `a` the discount.
  Selecting only `b` keeps discount `0`, even if the input/scope order reverses.
- Charges `a = 1`, `b = 1`; no discount; tax `5000` bps on both. Whole tax is `1`;
  either one-line approved subset has tax `1`. Independently calculated
  complementary subsets need not add to the original rounded tax. The declined
  subset is not a second sale or remaining amount to collect.
- Selecting a zero-price charge is still a real selected line. A nonempty
  approved set can have total zero; money > 0 is not the approval predicate.

This policy is a disclosed quote-pricing primitive, not fiscal compliance. A
conditional bundle discount whose terms cease to apply when any line is declined
cannot use this unconditional allocation policy: produce a new quote revision
with the intended terms and obtain fresh approval. The future review/commit UI
must show the exact subset breakdown before a decision is recorded. There is
no silent re-pricing after the customer decides.

## 6. Append-only corrections, stale state and replay

### 6.1 Ordering and command proof

Every **decision** command has a required caller-stable `decision_id` (also the immutable
entry ID), the exact target `(lineage_id, quote_id, quote_version)`, the expected
current head `(quote_id, version)` and `expected_decision_sequence` for the whole
lineage. Sequence/version inputs use the existing exact-integer rule (no bool or
coercion); the empty decision ledger has sequence 0. New entries get contiguous
sequence `previous + 1`; neither timestamps nor quote version substitute for it.
Revision append is a separate command family described in section 6.3.

Store the complete canonical semantic command proof alongside the result in
memory. It includes scope, recording actor, target, outcome/selection, maker,
channel, decision time, evidence note/reference, expected head/sequence and
correction target/reason/mode. Canonicalization copies and orders selections;
it does not trim/alias identifiers or erase evidence changes. Recording time is
server-supplied execution metadata; it is stored in the result, not allowed to
turn an exact retry into a new command. Supplied changed `recorded_at` on a retry
never rewrites the original time.

Keep one immutable canonical command value bound to each entry, rather than an
independently mutable receipt index. Reconstruction compares every proof/result
fact: ID, actor, scope, target, outcome/selection, maker/channel/decision time,
source/note, correction mode/target/reason and sequence. The expected sequence
must equal the actual pre-append sequence. The observed head must identify a
real prefix of the supplied history with the chronology in section 4.3;
every admitted decision/correction/withdrawal targets that prefix head. Reject
orphan/missing/
duplicate proofs, mismatched actors or facts, conflicting IDs and branching
correction chains. Recomputed money alone is insufficient validation.

Process in this order:

1. Validate command shape and scope against the supplied ledger. Do not yet
   apply current-head, new-entry timestamp, correction-admission or order-state
   rules; those would incorrectly reject a valid historical exact replay.
2. If the ID exists, compare the canonical proof including actor. An exact match
   returns the original entry and emits nothing; any semantic mismatch is an
   idempotency conflict, even if current optimistic preconditions are stale.
3. For a new ID, require exact expected current head and decision sequence. A
   mismatch is an explicit stale conflict with no effect.
4. Apply the new-decision or correction rules, compute pricing and append one
   entry plus one domain-event intent.

Exact replay of an older accepted decision remains a valid replay after a new
revision or correction. It is **historical receipt success**, not renewed
approval: return current applicability separately, never return a stale entry
as the current authorization. Reusing a new ID with otherwise identical content
is a new action and must satisfy all current preconditions/correction rules.
The future service must authorize access before even returning a replay.

### 6.2 New decisions and replacements

A new initial decision is allowed only for the current unsuperseded revision and
only if that revision has no earlier decision entry. Choosing to change a
recorded decision requires the explicit correction/replacement action with the
latest entry ID for that revision, a nonblank reason, and fresh evidence.

A replacement names `supersedes_entry_id`; a withdrawal does the same and records
who withdrew the record, when and why. Both target the current quote revision. Reject missing/cross-lineage/wrong-revision
or nonlatest targets, self-reference and branching replacement chains. Every
prior entry remains unchanged. A replacement is the complete new selection;
there is no cumulative merge of approvals. A decision after withdrawal links to
the withdrawal rather than resurrecting an earlier effective entry.

Separate correction purposes:

- `customer_change`: a new attested customer decision, current revision only,
  with its own maker/channel/decision time.
- `record_correction`: corrects the workshop's recorded evidence or selection
  for the current quote revision; it records the correcting staff actor and a
  required reason. It must not masquerade as a fresh customer act.
- `withdraw_record`: invalidates a recorded entry without asserting that the
  customer declined the work; requires its one `EntryRecording` with actor,
  reason and time, not a fabricated maker/channel/decision time. A withdrawal
  carries no new customer decision evidence. A later replacement supplies fresh
  evidence and links to the withdrawal.

New corrections/withdrawals targeting a superseded revision are refused, even
with the current head precondition and an existing historical entry. That edit
mode is deferred to a separately reviewed history policy; it is not an automatic
repair route. Preserve old entries unchanged and continue exact historical
replay. A first late approval of an old revision, or an approval allegedly made
after supersession, cannot be admitted through `record_correction`.

### 6.3 Revision after approval

Appending any new revision makes the prior approval historical, even if its
lines happen to be equal. The new head starts with `NO_CURRENT_DECISION`.
No approval, rejection, stock reservation, consumption or execution authorization
is copied. Previous entries and full pricing stay available as evidence of what
was approved then. The current projection is derived only from the latest entry
for the current revision and reports rejection/withdrawal explicitly.

QuoteHistory revision and ledger operations must be composed through the same
new aggregate so its decisions cannot be accidentally detached or lost on
revision. Revision append also checks the expected current head and decision
sequence; it must not discard a decision that won since the revision was drafted.
Its creation time obeys section 4.3's cross-operation chronology. Revision append
returns the updated aggregate and the existing `QuoteRevision` pair, preserving
all decision entries and the unchanged decision sequence. It appends no decision,
manufactures no `QuoteDecisionRecorded` intent and does not change Task 4's
revision-ID behavior. Failed operations return no changed aggregate or intent.
Concurrent writers operating on detached snapshots still need future database
serialization; in-memory CAS tests are not PostgreSQL race evidence.

## 7. Order lifecycle and inventory boundary

### 7.1 Pure domain delivery

A successful recorded decision yields a typed `QuoteDecisionRecorded` domain-event
intent with event ID equal to the entry ID, order/scope, exact revision/sequence,
outcome, approved/declined line IDs, pricing and an internal `decision_id` entry
reference. It contains no raw optional source reference, note, correction reason
or full evidence object. Corrections and withdrawals have explicit kinds and
predecessor IDs. This is an in-memory value, not an inserted `ServiceOrderEvent`,
outbox message or notification.

The pure result does **not** mutate a `ServiceOrder` or execute an inventory
command. The initial-transition planner takes the **current supplied aggregate**,
order snapshot and decision result/entry identity together. A retained successful
result alone is insufficient. Require all of the following:

- Exact organization/location/order/lineage identity, and order `DIAGNOSIS`.
- The result is a non-replay newly appended initial decision; its canonical
  command/receipt belongs to that aggregate. Its target is the aggregate's
  current head, its entry is that head's latest effective entry, and its receipt/
  selection/pricing match the aggregate's current decision projection.
- Its returned head and decision sequence match the current aggregate. It must
  be the newest appended entry; a subsequently appended revision, replacement,
  withdrawal or any other newer decision entry makes the retained result stale.

Only then map initial full/partial approval to `authorize` or initial rejection
to `reject`. The plan carries the exact order ID/version, lineage ID, head
ID/version, decision ID/sequence and action as explicit consumer preconditions.
Rejection is a current applicable decision with an empty approved set, not an
approved-work projection. Replay/correction/withdrawal never yields an initial
transition plan; missing/foreign/mismatched or historical receipts yield an
explicit refusal. No `AUTHORIZED -> REJECTED`, reset to `DIAGNOSIS`, or new
partial state is added.

The planner proves freshness only against its supplied immutable snapshots;
it cannot prove canonical reads or prevent a caller reusing an old aggregate
alongside an old result. Future transaction-time authorization and revalidation
of **all** plan preconditions are mandatory before consuming a plan. Unit tests
may pass a fresh plan to the unchanged `ServiceOrder.transition` to prove action
compatibility. No live route, state-machine change or durable plan consumption
is implemented here.

### 7.2 Later orchestration requirements, not delivered behavior

Before any connected quote workflow is activated, the application service must
atomically check current principal/capability and scope, lock/read the order and
quote lineage, recheck both versions and decision sequence, persist evidence,
apply any legal initial transition, and append structured timeline/audit/outbox
records exactly once. Existing transition events cannot store structured quote
associations; choose a reviewed additive persistence projection, not note text.

For a revision/correction after the initial order transition, quote coverage can
change while the historical order state remains `AUTHORIZED` or later. Do not
rewrite order history or pretend that state alone is current quote consent.
The connected workflow must gate new work/reservation against current approved
line coverage. Updating a quote must not reverse already-performed work or
consumed stock. Re-consent, rejection after work starts, resumption of a rejected
order and safe handling of outstanding holds require a separately reviewed
application policy before those paths are exposed. Until then such operational
paths remain blocked, although the pure evidence ledger can represent them.

This deliberately bounds Task 5: it is decision evidence and a compatible
initial-transition plan, not a claim that all plan Tasks 5–12 are delivered or
that existing generic order actions have become quote-aware.

### 7.3 Reservations are separate commands

Approval produces no stock movement, automatic reservation, release, consumption
or availability promise. The existing online inventory API does not currently
check quote decisions and is unchanged [S6]. Later order-linked stock commands
must explicitly validate current approved part-line coverage and their own
stock/idempotency/authority rules. Multiple same-product quote lines still have
distinct IDs; no implicit merging or duplicate reservation follows approval.

Outstanding reservations are not silently dropped when consent changes. Their
reconciliation is a separate reviewed command workflow. Preserve whole-hold
RELEASE/CONSUME and atomic `CONSUME +n` with `ADJUST -n`; no partial finalization
or new reservation identity is invented after an unknown command outcome [S6].

## 8. Security, compatibility and next-slice constraints

The business word "authorization" here means customer approval evidence; it is
not server access authorization. This pure module grants no user capability.
The actual catalog currently has no `quotes.*` literals [S7]. Do not widen
frozen legacy wildcard/role sets, infer owner adoption or add grants in Task 5.

Future persistence/API work needs its own capability/admission compatibility,
closed DTO/money transport, current-authority barrier, body bounds, no-store,
PII minimization, concurrent CAS/replay and structured audit review. Offline
quote drafts remain drafts; client evidence alone cannot authorize a server
write. Today's sync mutation entity union remains closed [S8]. No new entities
are added to the existing baseline/protocol by this ADR.

Actual inspected SQL head is `0011_workshop_branding`, following `0010`; actual
authenticated local schema is **7**. Branding reserves future quote SQL **0012**
and local **8** [S9]. Earlier plan SQL0010/local6 and arithmetic ADR SQL0011
reservations are historical. Reinspect the real chain when persistence work
starts; create no empty reservation and rewrite no applied migration. Task 5
creates no migration or local schema change.

## 9. Rejected alternatives

- Reinterpreting `quote_id` as lineage ID breaks the existing revision contract.
- Using `(order_id, version)` alone cannot distinguish independent histories and
  weakens exact-reference evidence.
- Carrying approval by stable line IDs into newer revisions approves unseen
  price/scope changes.
- Applying the full fixed discount or tax to a subset over/understates consent.
- Reallocating the same fixed discount among fewer lines silently changes their
  accepted per-line economics.
- Creating a quote revision for every unchanged subset selection obscures the
  actual offered revision. Use a new revision when terms change, not merely
  when the customer declines lines.
- Mutable approval flags, timestamp last-writer-wins or cumulative partial sets
  lose audit/intent or merge incompatible decisions.
- Treating evidence correction as reverse order/stock execution changes history
  and exceeds this domain-only slice.

## 10. Risk and test matrix (planned, not executed)

| ID | Invariant / risk | Required failing-first and acceptance cases |
| --- | --- | --- |
| QD-01 | Revision versus lineage confusion | Root identity; 3+ revisions; exact predecessor/successor/time/scope; reject missing root, gaps, branch/cycle and any reused revision ID; source snapshots unchanged. |
| QD-02 | Line identity reuse transfers consent | Reorder preserved; kind/product replacement rejected with same ID; new ID accepted; removed/reintroduced ID rejected; changed value same ID allowed only in new revision and never inherits approval. |
| QD-03 | Partial selection ambiguity | Full/none/proper subset; all charge kinds and zero prices; duplicate/foreign/tax/discount IDs; all/empty partial rejected; complement explicit; immutable copied collections. |
| QD-04 | Lost discount pennies | Independently computed Fraction/integer oracle; ties, odd subtotals, zero gross members, multiple overlapping valid discounts and selected shares; retain existing overdraw rejection. |
| QD-05 | Tax is copied or rounded incorrectly | Empty/intersecting/full bases; overlapping taxes, zero/10000 bps, half-up ties, >2^53 money; no tax per-charge rounding; nonadditive complementary example. |
| QD-06 | Full approval diverges from Task 4 | Exact original subtotal/discount/tax/total for all valid fixtures and generated cases; arbitrary presentation/scope/selection permutations identical. Existing 106 Task 4 tests retained. |
| QD-07 | False evidence provenance or contradictory chronology | One recorder/time per entry; maker distinct; every channel and invalid identity/enum; timezone and active-interval limits; approval then backdated revision rejected; equal-time boundary accepted; current correction with earlier valid decision time accepted; all new corrections/withdrawals of superseded evidence rejected, including old rejection -> alleged post-supersession approval and valid old-interval late recording; original history preserved; same rules on reconstruction. |
| QD-08 | Historical correction destroys intent | Initial -> replacement -> withdrawal -> new replacement; all ancestors equal; complete selection replacement; reason mandatory; wrong revision/missing/nonlatest/self target denied. |
| QD-09 | New revision revives/loses evidence | Approve v1 -> revise v2 -> no current coverage; new v2 decision; new v1 correction/withdrawal and first late v1 approval refused; original v1 exact replay returns historical receipt plus current projection; original history/prices unchanged. |
| QD-10 | Replay duplicates effects or changes actor | Same ID/semantic proof returns same entry/time, no event; reordered selection exact; changed actor, maker, evidence, scope, outcome, expected head/sequence or correction target conflicts; old exact retry remains historical after correction/revision. |
| QD-11 | Competing detached decisions silently merge | Apply A then stale B against resulting ledger rejects; stale head, version and decision sequence independently rejected; decision vs revision in both serial orders; no claim that these tests prove database locking. |
| QD-12 | Stale evidence authorizes an order or state expands | Fresh current initial approve/partial -> existing authorize; reject -> existing reject; retained D1 after revision/withdrawal/replacement refused; historical correction while v2 current refused; unrelated same-scope lineage and receipt absent from ledger refused; exact plan order/head/decision preconditions; every non-DIAGNOSIS state refused; corrections/replays no plan; original state table unchanged. |
| QD-13 | Approval mutates inventory | No inventory/service/DB/network dependency; result contains no stock commands; input order/ledger unchanged; part IDs and quantities remain exact snapshots. |
| QD-14 | Financial precision/coercion | Existing integer-only rejection of bool/float/Decimal/string; generated large exact values; aware UTC normalization; no caller total accepted; wrong reconstructed pricing fails. |
| QD-15 | Broader scope sneaks into delivery | Diff checks: no migrations, OpenAPI/generated client, capability catalog, sync union, local schema or UI change. Repository contracts and unchanged existing tests pass. |
| QD-16 | Proof, receipt and projection disagree | Reconstruction equals incremental result; every proof fact matches its entry, including actor/mode/target; orphan/duplicate/missing proof and backward or nonexistent observed-head prefix refused; expected sequence equals actual pre-append sequence; historical receipt returned with current aggregate/projection; new retry recording time ignored; revision preserves entries/decision sequence and emits no decision event. |

Run the new smallest regressions RED before domain implementation, then focused
GREEN, all quote/order/inventory domain regressions, Ruff/format/mypy, relevant
repository contracts and the repository qualification ladder appropriate to the
final changed tree. Record test names, counts, exact commit and real skip/blocker
reasons. Documentation-only review now uses source checks, link checks and
`git diff --check`; no authored table row is test execution evidence.

PostgreSQL races/migrations, native offline/reload/two-client behavior, review/
commit UI and four-theme accessibility, restore/deployment, physical Windows/
Android/Raspberry and manual screen-reader/touch/glare remain later independent
gates. Pure-domain tests cannot close them.

## 11. Review gate and finite implementation outline

Independent review accepted the amended contract after closing initial-planner
freshness, chronology and six evidence/replay precision findings. The reviewed
proposal had SHA-256 `28fc49f90012a0261adc026fa3b3c7276cfef508c2f012c5ad0eff4096bc44b4`.
This status change records contract acceptance, not implementation qualification.
Independent source review and the test/evidence gates below remain required.

After acceptance, the smallest expected patch is new pure quote history/decision
values/helpers, one private shared allocation helper if needed, initial/replacement/
withdrawal operations for the current revision with proof-bound replay/current
projection, the bounded fresh-initial planner, focused tests and an evidence/state
entry. New edits to superseded evidence are explicitly deferred, while immutable
historical receipts and exact replay remain covered. No generic
event-sourcing framework, reusable idempotency service or policy engine is needed.
Preserve all 106 accepted Task 4 tests, quote public results and existing
order/inventory behavior. Do not claim durable timeline delivery, security or a
complete money-and-parts journey. Stop for review at that domain-only candidate;
Task 6/8 persistence/API design is a separate gate.

## 12. Sources inspected at the baseline

- **S1:** [Functional requirements](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md),
  lines 65–76, 176–185, 199, 207–208, 237–240: state machine, quote/decision/
  timeline, offline history, currency and exact-version/compensation rules.
- **S2:** [Accepted quote arithmetic/history ADR](2026-10-13-quote-arithmetic-and-history.md),
  sections Input and money boundaries, Calculation phases and History, lines
  20–84: integer inputs, original allocation, rounding and immutable revisions.
- **S3:** [Increment 2 plan](../superpowers/plans/2026-09-01-v0.2-increment-2-budgets-inventory.md),
  lines 5–25 and 81–136: Task 5 intent and subsequent persistence/API/offline/UI/
  E2E work; old schema reservations are superseded as described above.
- **S4:** `services/platform/src/cycling_workshop/quotes/domain.py:125–184,187–306`;
  `services/platform/tests/quotes/test_quote_domain.py`: accepted allocation,
  public totals, revision links and existing regression suite.
- **S5:** `services/platform/src/cycling_workshop/service_orders/domain.py:32–41,67–103,138–182`;
  `service_orders/schemas.py:9–20,65–73`; `service_orders/repository.py:50–63`:
  existing transitions, event shape and persistence boundary.
- **S6:** [Accepted inventory atomicity ADR](2026-10-13-inventory-command-atomicity.md),
  lines 21–55, 59–81: independent online commands, authority/replay, whole-hold
  finalization and atomic consumption pair.
- **S7:** `services/platform/src/cycling_workshop/identity/roles.py:8–57,82–99`;
  [branding ADR](2026-10-14-shared-workshop-branding.md), lines 25–67: explicit
  catalog and frozen legacy grants/compatible future adoption.
- **S8:** `services/platform/src/cycling_workshop/sync/schemas.py:11–20`;
  [security specification](../03-security-privacy/open-cycling-workshop-platform-phase-3-security-privacy-threat-model-v0.1.md),
  sections 8–11, 13–14 and 18: server reauthorization, evidence, minimal PII,
  one-time portal scope and append-only audit.
- **S9:** `services/platform/migrations/versions/0011_workshop_branding.py:12–13`;
  `apps/web/src/access-kernel/database.ts:65–73`;
  [branding ADR](2026-10-14-shared-workshop-branding.md), lines 71–75, 142–146;
  `docs/10-spec-development/execution-state.yaml:1171–1179`: actual and future
  schema numbers. No new schema is established by this proposal.
- **S10:** [UX specification](../04-ux-design/open-cycling-workshop-platform-phase-4-ux-ui-design-system-v0.1.md),
  lines 128–138, 294–312: quote review/commit and accessibility;
  [finite MVP plan](../10-spec-development/2026-10-14-local-workshop-mvp.md),
  lines 38–46, 59–65: money/parts outcome and physical/operator gates.
- **S11:** `AGENTS.md`, [Master Agent Loop v0.2](../10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md),
  `docs/10-spec-development/execution-state.yaml` and `MANUAL-ACTIONS-CHECKLIST.md`:
  source precedence, TDD, append-only financial history, evidence and stop rules.

This document contains no customer data, external consent record, credentials,
legal agreement, fiscal-compliance assertion or authorization to deploy.
