# ADR: bounded quote persistence and initial online commands

- **Status:** Accepted for repository-first Task 6 on 2026-10-15. Later application
  and activation stages retain every gate below. See the
  [acceptance record](../10-spec-development/2026-10-15-quote-persistence.md#architecture-acceptance).
- **Date:** 2026-10-15.
- **Inspected source:** `9d8dcd5f80d036f0fb7a0407584bb761dad83e95`, tree
  `ac1e5985e7bb89a274755e9ab0bcb2d1ec35778a` (reviewed Task 5 pure domain).
- **Scope:** Increment 2 Tasks 6/8 and the initial durable part of Task 5.
  ADR acceptance itself changes no schema, application behavior, grants or installation.
- **Requirements:** FR-SVC-005/007/008/009/016, BR-004/005/006/007,
  OFF-005/008/009/012, SEC-002/003 and NFR-009.

## 1. Decision and delivery gates

Keep the accepted [arithmetic/history](2026-10-13-quote-arithmetic-and-history.md)
and [decision/partial-pricing](2026-10-15-quote-decisions-and-partial-pricing.md)
contracts. Persist one complete, immutable revision/decision history per service
order. Expose a deliberately bounded online initial-consent contract only after
fresh authority, atomic receipts and legacy-route fences exist. A database row
or historical approval alone must never become current execution permission.

Deliver and qualify separately:

1. **Repository first, Task 6:** additive migration, models, complete strict
   reconstruction, atomic repository operations and real PostgreSQL/restore
   tests. No quote routes, catalog additions, grant adoption, operational
   enrollment, sync entries or UI activation in this slice. Synthetic repository
   tests may exercise current-revision replacement/withdrawal supported by the
   domain; that is not an exposed correction workflow.
2. **Read boundary, partial Task 8:** scoped online reads, bounded DTOs and
   regenerated contracts may follow. Capability/catalog compatibility must be
   qualified before these protected routes are exposed. Reads do not enroll an
   order and cannot authorize work. Existing orders receive no fabricated quotes.
3. **Initial command boundary, partial Tasks 5/8:** create/revise/initial decision
   routes can be exposed only together with the enrollment and all-route fences
   in section 7, atomic effects in sections 3/6, and their PostgreSQL/security
   tests. Until then, do not register externally reachable quote mutation routes;
   an undocumented feature flag is not an alternative gate.

Even stage 3 does not activate execution or stock for quote-managed orders:
section 7 intentionally blocks those operations pending a separate line-coverage
integration. Full Task 5, the quote/inventory journey and Increment 2 remain
incomplete. No offline product/quote entity union, baseline, journal, IndexedDB,
editor, portal, notification delivery, payments or generic event framework is
introduced here. Tasks 7/9/10/11 retain their own acceptance gates.

Actual SQL head is `0011_workshop_branding`; reserve **0012 after 0011**, rechecking
immediately before implementation. Authenticated local schema is **7**; **8** is
only a future quote reservation. Do not add an empty migration, rewrite applied
history, widen local stores or backfill old orders. [S1]

## 2. SQL model and immutable reconstruction

Use these quote-owned records; names describe the intended model, not ready DDL:

| Record               | Identity and invariant                                                                                                                                                                                                                                                                                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quote_lineages`     | Root revision ID is the lineage ID. Unique `(organization_id, order_id)`; immutable organization, location, order and currency. Only current head ID/version and decision sequence are mutable CAS fields.                                                                                                                                                                      |
| `quote_revisions`    | Immutable revision ID; unique `(lineage_id, version)` and at most one successor per predecessor. Root is version 1 and has no predecessor; each successor identifies the immediately preceding revision. Save actor/time and computed totals.                                                                                                                                   |
| `quote_lines`        | Immutable `(revision_id, line_id)`, discriminated kind, typed integer values and description/product/price snapshots. Save input position as presentation order, unique within revision. Never refill history from live product prices.                                                                                                                                         |
| `quote_line_targets` | Immutable discount/tax-to-charge associations, composite same-revision foreign keys and unique source/target pairs. Charge kind and valid allocation remain strict domain checks.                                                                                                                                                                                               |
| `quote_decisions`    | Immutable decision ID, lineage sequence, exact revision, recording metadata, per-line decision and full subset-pricing snapshot. Unique `(lineage_id, sequence)` and same-lineage/revision predecessor reference for replacement/withdrawal.                                                                                                                                    |
| `quote_operations`   | One immutable terminal receipt/audit fact per successful create, revise or decision command. Unique `(organization_id, operation_id)` across all three kinds; exactly one revision or decision result reference, canonical versioned proof, actor/time and structured effect references. No pending/out-of-transaction receipt and no second independently mutable proof index. |

For a decision, `operation_id == decision_id`; create/revise also require a
caller-stable operation ID, distinct in purpose from their caller-provided new
revision ID. The canonical domain command exists once, nested in the operation
proof; reconstruction joins its one decision result to build `QuoteDecisionEntry`.
Reject missing, duplicate, extra or mismatched proof/result pairs. Stored FK/index
columns that repeat proof facts must compare equal. The operation table is a
finite quote module concern, not the sync mutation table or a reusable command bus.

Composite FKs bind all quote children to the same lineage/tenant and revision.
Add the minimal unique order key `(id, organization_id, location_id)` needed for a
lineage FK; do not accept redundant location facts merely because each belongs
to the tenant. Product references bind tenant and are checked against order
location on admission. Actor references bind tenant. Keep customer/order identity
from the locked order; maker evidence is independently validated in section 5.

Head/root references use deferrable same-lineage revision FKs, allowing insertion
of root lineage/revision in one transaction without a committed null head.
Checks require positive revision versions, nonnegative decision sequence and a
head ID/version pair naming the same stored revision. Root ID equality, contiguous
history, retained line kinds/product IDs, retired line identities, correction
chains and chronology are verified by the existing domain on every reconstruction;
SQL uniqueness/FKs do not replace those checks. The first order lock and unique
order/lineage key serialize two initial creates even before a lineage exists.

**No predecessor update:** derive `superseded_by` and `superseded_at` from the
unique successor and its creation time when mapping to `QuoteHistory`. This
satisfies the pure revision pair without rewriting a persisted financial row.
Load the complete ordered history and all decision/proof pairs, run the canonical
domain constructors, recompute every stored total/allocation and compare the
lineage head/cursor. Never validate just a page, repair corrupted evidence on
read, infer a missing ancestor or treat the largest surviving version as a head.

All revisions, lines, associations, decisions and operations receive database
append-only UPDATE/DELETE guards. Retention FKs use `RESTRICT`, including the
lineage's order/organization dependencies; no cascade may erase quote evidence.
Only the lineage cursor may update through CAS. No delete endpoint, automatic
archive or destructive downgrade is provided. Forward-only recovery and approved
restores preserve the full chain. These controls protect ordinary application
writes; they do not claim to defeat a privileged database operator. [S2]

## 3. Fresh admission, semantic retry and one transaction

### 3.1 Authorization and lock order

Use the existing protocol-1 admission and original signed-session principal.
Acquire **organization → fresh actor → order → lineage** before receipt/domain
reads; use `populate_existing` after waits. Preserve the exact existing
`lock_writer` rule: intersect fresh persisted actor literals with the
**already-narrowed incoming principal**, itself restricted by the original token.
Do not restore a literal removed by initial authentication but re-added while
waiting by recomputing only raw-token/final-account intersection. Retain active
and session status, tenant/location, dataset incarnation, protocol floor and
expiry. Use existing PostgreSQL lock and statement limits, without per-quote timeout increases to make tests pass.
Do not raise tenant floors or run adoption as a side effect. [S3]

Every read requires `quotes.read` and `orders.read`. Every create/revise requires
those plus `quotes.write` and `orders.write`; enrollment changes which operational
paths the order may use. An initial decision requires `quotes.read`,
`quotes.authorize`, `orders.read` and `orders.write`, not `quotes.write` by
implication. All operation grants and scope are required even for exact replay.
No role/owner shortcut and no authorization inferred from a maker ID. Reads use
fresh current authority too, not an offline admission snapshot.

Resolve an order and operation only within the admitted scope. A foreign and
nonexistent target have the same non-disclosing response. Do not expose a receipt
collision from another scope, or read evidence merely because its ID is known.

### 3.2 Proof contract, version 1

After strict shape validation, form one canonical semantic value containing:

- proof version and quote operation kind;
- authenticated organization/location/order/recorder identity and operation ID;
- exact target lineage/revision IDs, the new revision ID for create/revise, and
  expected order version, head ID/version and decision sequence;
- all accepted typed lines/currency or decision outcome/selection/evidence fields;
- for repository-only corrections, exact mode, predecessor and reason.

First create uses explicit absent-head values (`null`, version 0, sequence 0).
Existing-lineage commands require exact positive head version and nonnegative
sequence. Scope/actor are derived by the adapter, never trusted request fields.
Server creation/recording time and generated effect IDs are result metadata,
not proof inputs. A retry does not get to change their original values. Protocol
headers, session version, authorization epoch and dataset incarnation are also
outside semantic proof; validate them wherever required by the existing admission
contract. This introduces no new quote REST epoch header. Fresh authority and
incarnation checks remain mandatory. After an authorized restore/incarnation
rotation, the same actor with newly valid admission can replay the old command
without restoring prior authority or creating new effects.

Canonicalization uses domain-normalized descriptions, UTC instants at exact
microsecond precision, sorted selection/target ID sets, and preserved nonblank
note/source/reason strings. Duplicate IDs fail rather than being deduplicated.
Revision line-array order remains significant as stored presentation order;
reordering only a decision selection or a tax/discount target set is equivalent.
Optional absent fields and explicit `null` normalize to the same declared null
value. All unknown fields fail. Store the canonical value with its version;
compare the complete value, not only a hash or raw JSON byte string. The sync
raw-body proof helper is not the quote proof implementation. [S4]

For an existing scoped operation ID, an exact proof returns its immutable receipt
plus a separately reconstructed **current** head/decision/order projection and
`replayed: true`. The current-order value is a closed projection of scoped IDs,
state and version only, not the existing full order payload or its legacy text.
A changed proof conflicts, including changed authenticated actor, expected order
version or evidence. Do this before new-command head,
DIAGNOSIS, history-limit or enrollment checks, so a committed command remains
retryable after transition, revision, cancellation or a later policy fence.
Fresh authority/incarnation and valid reconstruction are still mandatory; historical
receipt success never reauthorizes work. A new ID is a new command, not an alias.

### 3.3 New operation and commit

For a new ID, check the activation/enrollment policy, exact order version/state,
head/sequence, current product scope and all limits. Reconstruct canonical history,
then call the pure ledger. Never replace CAS with timestamps or last-writer-wins.
Use trusted UTC execution time; if it would violate established chronology,
refuse without effects rather than backdating or silently moving evidence.

An eligible initial decision must pass the existing freshness planner against
that same locked current aggregate/order and its just-appended non-replay result.
Recheck every returned plan precondition, then use the existing state machine for
`authorize` or `reject`. Save receipt, history/cursor, actual order event/version,
existing order change-feed projection and quote outbox association atomically.
Quote creation/revision alone does not bump order version or add a fake order
state event. Build and size-check the complete bounded quote response before
commit; a delivery failure after commit is a receipt-replay case. Recheck expiry
immediately before explicit commit. Every failure, including serialization, projection or outbox failure, rolls back every effect.

A response lost after commit is recovered with the same operation ID and proof;
a transient/deadlock retry does not invent a new identity. No visible intermediate
success, side transaction or durable receipt detached from its effects is allowed.
No automatic replay of effects during reads, restore or reconstruction. [S3,S8]

## 4. Explicit quote grants and old-client compatibility

Add a separate `QUOTE_CAPABILITIES = {quotes.read, quotes.write, quotes.authorize}`
only in the application-boundary slice, not the schema migration. This one
explicit catalog addition may accompany read-only routes: a recognized grant
is not a claim that its mutation routes are registered. Those remain absent
until stage 3; granting a literal cannot bypass that gate. **Never append
them to `BUSINESS_CAPABILITIES`: frozen legacy role bundles derive from that set.**
Keep the seventeen-grant legacy wildcard, `LEGACY_ROLE_BUNDLES`, v1 role-string
aliases/catalog, stored grants and old token snapshots unchanged.

The current v2 catalog remains shape/version 2. Add the three explicit literals;
only its new **Owner** starter snapshot adds all three. Other current starter
bundles remain unchanged, including empty TechnicalAdmin. Administrators may
assign individual literals only through the existing explicit-grant rules, with
no greater authority than their own current grants. Existing owners retain their
old grants on unrelated edits; explicit new-owner creation/promotion/grant
replacement continues to require the full current set. Role selection itself
never evaluates to live authority.

The later accepted branding ADR's compatible-addition clarification governs the
earlier context ADR's general catalog-bump wording: retain
`ocwp-access-baseline-2`, unchanged epoch algorithm and existing operational
read maps. Existing accounts gain no quote authority and keep their old epoch.
Actual explicit quote grant changes alter the existing derived epoch; adoption
also revokes prior sessions. If implementation needs a new read-map/entity or
changes prior grant resolution/epoch meaning, stop for a negotiated protocol ADR
instead of using this compatibility exception. Old clients keep their existing
workflows and fail closed on editing unknown new grants. [S5]

Bootstrap of an established tenant needs a **separate explicit local quote-only
adoption command**, following the reviewed branding pattern: active established
organization-wide owner, expected account version, append only missing quote
literals, preserve all unrelated values, identity audit and session-version bump
in one transaction. Do not extend the branding-only command, run either command
from migration/startup, or adopt for every owner. An installation may deliberately
establish a new full-current owner through the existing explicit first-owner
establishment path (`identity/admin_cli.py:create_first_owner`). Legacy
installation bootstrap still creates its unchanged location-scoped wildcard
administrator; it does not acquire quote grants or become an owner.
The complete migration chain must exist before adoption; grants alone do not
activate routes. Implementation tests use synthetic accounts. Running adoption
against any real account requires separate operator authority and is outside
this ADR task.

## 5. Bounded persistence and REST contract

### 5.1 Exact numbers and finite resource limits

The connected adapter chooses **exact JSON integers**, not decimal strings.
`MAX = 9_007_199_254_740_991` (2^53−1). Monetary inputs and nonnegative totals or
allocations are 0..MAX; a discount amount is 1..MAX; signed `line_amounts` may be
−MAX..MAX. SQL monetary columns use BIGINT with matching checks. Reject booleans,
floats/exponent syntax, numeric strings, non-finite values and coercion. Calculate
with Python integers, then range-check **every** stored/returned intermediate
line amount, subtotal, allocation, tax and total before any durable effect.
Internal multiplication may exceed MAX; exact final bounded results may not.
The pure domain remains arbitrary precision and all existing tests stay intact.
Currency remains an explicit three-uppercase-ASCII-letter code; this ADR neither
assumes two decimals nor introduces a hard-coded ISO/tax jurisdiction catalog. [S6]

| Boundary                                                  | Chosen limit                                                                                                                                                                                                                                                                                                                   |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Raw request                                               | 128 KiB UTF-8, enforced while streaming before parsing or locks; no trust in Content-Length. Reject compressed request bodies.                                                                                                                                                                                                 |
| JSON                                                      | Depth 12; duplicate object keys, non-finite constants, malformed UTF-8 and unknown fields refused. Validate bounded integer lexemes before constructing arbitrary-sized integers.                                                                                                                                              |
| One revision                                              | At most 100 total typed lines, at least one charge, at most 1,000 total discount/tax target edges.                                                                                                                                                                                                                             |
| Quantity/minutes; tax                                     | 1..1,000,000; tax 0..10,000 basis points.                                                                                                                                                                                                                                                                                      |
| Text                                                      | Description 500 codepoints/2,000 UTF-8 bytes; note 2,000/8,000; reason 500/2,000; source reference 200/800. Check raw and normalized bounds, reject U+0000, lone surrogates and malformed UTF-8; never truncate evidence.                                                                                                      |
| IDs/times                                                 | New quote, line, decision and operation IDs are canonical UUIDv7; existing order/customer/product/actor references retain existing bounded ID compatibility (1..36 characters) plus scoped lookup. Evidence timestamps are RFC3339 timezone-aware instants, at most six fractional digits, normalized to UTC without rounding. |
| Versions/cursors                                          | Exact safe JSON integers; positive versions, decision sequence 0..MAX. Counts below impose tighter practical limits.                                                                                                                                                                                                           |
| Complete lineage                                          | At most 32 revisions and 128 decision entries; at most 16 MiB of canonical reconstructed financial/evidence/operation records combined.                                                                                                                                                                                        |
| Single stored logical revision or decision with its proof | At most 256 KiB of canonical UTF-8 JSON. Validate JSON-resident money/shape on both write and reconstruction.                                                                                                                                                                                                                  |
| REST results                                              | Maximum 1 MiB serialized response; metadata history pages default/max 25, opaque scoped continuation, no raw proof included. Individual immutable revision/decision detail is bounded separately; no full-history response.                                                                                                    |
| Errors                                                    | At most 8 KiB, bounded error count, no raw request/evidence echo.                                                                                                                                                                                                                                                              |

These are adapter/storage admission limits, not changes to pure constructors.
Use one versioned canonical serialization to measure record/history byte budgets;
count each logical record/proof once, excluding indexes/storage-engine overhead.
Check each dimension against the candidate aggregate before commit and refuse
only a command that would exceed a boundary. At revision 32, a decision can still
fit the decision/byte budgets; revision 33 cannot. Likewise reaching the decision
count does not itself forbid a revision that fits all other budgets. Keep all
existing reads and exact retries. Never truncate, delete or start an unrelated second lineage to evade a limit. Any larger transport
range or history-retention strategy requires a later reviewed contract. Qualify
maximum fixtures under existing transaction limits; a failed capacity test blocks
activation, not permission to weaken bounds or omit validation.

### 5.2 Initial endpoints and evidence provenance

Retain the plan's route families. `POST /api/v1/service-orders/{id}/quotes` accepts
a closed discriminated create/revise request with operation ID, new revision ID,
expected order/head/sequence and complete typed lines. Currency is supplied on
create; revision cannot change it. GET on that collection returns bounded revision
metadata; direct immutable detail and quote timeline reads are separately typed.
`POST /api/v1/quotes/{revision_id}/authorize|reject|authorize-partial` takes the
exact lineage/head preconditions and evidence; outcome follows the route and
whole-line selections follow the accepted domain. No client totals, prices inside
approval, authenticated-recorder override or server timestamps are accepted.
Regenerate OpenAPI and the TypeScript client; avoid `any`/unbounded-number DTOs.

The first online decision surface supports only an attested **customer** maker
whose ID equals the locked order customer, with in-person/phone/email/messaging/
written channels. A staff recorder attests the evidence; this is not customer
login or cryptographic signature. Representative relationship authorization and
`portal` provenance are not modeled today, so both are explicitly deferred and
refused at this surface. Repository reconstruction still preserves all valid pure
domain evidence kinds; it must not reinterpret historical records. New customer
changes, record corrections, withdrawals and decisions after the initial order
transition have no route in this slice. New superseded-evidence edits remain
refused, while exact historical retry stays supported.

Every quote success/error, including malformed/oversized input, uses private
`Cache-Control: no-store` and a server-generated correlation ID. Cover both nested
service-order and direct quote paths in middleware; current private-path lists
do not already do so. Do not log proof, source reference, free text or raw validation
input. This online API does not enter offline caches or grant an offline approval
capability. [S7]

## 6. Structured timeline, audit and outbox identity

Use `quote_operations` as the quote-specific structured timeline/audit source,
not a new generic audit framework. Each immutable fact links its actor/time,
lineage, exact revision and optional decision, plus the actual order event if
one occurred. Timeline order uses a stored, validated ordinal equal to the
**resulting revision version + resulting decision sequence**: root is 1 and
every successful revision/decision increases the sum by one. Unique
`(lineage_id, ordinal)`; retries add nothing. No additional mutable timeline
counter or timestamp-based ordering is needed. Validate the ordinal/proof/result
chain on reconstruction, including ordinal contiguity and equal-time operations.

Expose a separate bounded quote timeline DTO, with structured identifiers,
action, revision/decision sequence and safe pricing summary. Detail requires the
same read authority. Do not change the existing order-events wire shape, invent
from/to states for revision-only events, or place approval identity in free-text
`note`. The linked actual order event must belong to that order/tenant and match
the initial plan. Identity audit's user/location/organization enum is not widened
for ordinary quote operations; grant adoption still uses identity audit. [S8]

For each new operation enqueue exactly one quote event intent in the existing
transactional outbox. The outbox helper allocates its own event ID; save that ID
in the immutable operation receipt. For a decision, payload `decision_id` and
`domain_event_id` equal the immutable decision ID, while `outbox_event_id` remains
the separately allocated delivery identity. Creation/revision events instead
carry operation and revision IDs. Include scoped IDs, version/sequence, kind and
minimal pricing/selection facts; exclude raw evidence/note/source/reason.
An initial decision also writes the existing order projection/outbox event, so
its transaction deliberately has **one quote event plus the existing order event**,
not a claim of one message total. A receipt for the stage-3 application command
that consumes the freshly validated initial-transition plan saves the full
immutable effect tuple: **order event ID, resulting order version (expected + 1),
change cursor, order-outbox event ID and quote-outbox event ID**. Create/revise and
other repository-only decision receipts, including domain mode `initial` for a
later revision, retain their quote-outbox ID but have all order-effect fields
explicitly null. The pure decision mode alone never selects or proves an order
transition; the order-effect tuple is all present or all null, and only the
permitted application transaction may create it. Stage 3 always requires that
transition tuple for its admitted initial-consent command; repository-only
histories do not create another exposed workflow.

Extend the internal `append_change` helper only to return a small typed
`(cursor, outbox_event_id)` result; existing callers may ignore it, and existing
wire projections stay unchanged. Do not infer either identity from timestamps,
a current order row or a payload search. Validate one-to-one effect ownership,
scope and expected content, including actor/time/action where represented and
the accepted order version. Mutable outbox delivery bookkeeping (`attempts`,
`published_at`) is neither proof nor a reason to invalidate a receipt.

Retries never enqueue again. Delivery remains at-least-once; consumers deduplicate
by stable outbox event ID, and may correlate the domain decision ID. Restore must
not regenerate IDs or republish already-recorded effects as new commands. No
external notifier or irreversible stock/payment side effect runs inside commit.

## 7. Enrollment and legacy-bypass activation fence

Presence of the unique lineage means the order is **quote-managed** permanently;
there is no client-controlled bypass/enrollment flag or route to remove it.
Membership checks cannot fall back to legacy behavior because the caller lacks
quote-read authority or the current revision lacks approval.
Before first enrollment require current `DIAGNOSIS`, exact order version, and
**no existing order-linked inventory movement of any kind**. This conservative
rule avoids silently importing active/released holds or prior physical work.
Use an authoritative existence query, not the inventory repository's capped
`list_by_order` page. Also refuse contradictory recorded order history; normal
DIAGNOSIS cannot follow work under the existing machine. This does not prove an
absence of unrecorded real-world work. Existing progressed orders and earlier
stock history require a separate reconciliation policy.

Until first decision, create/revise are allowed only in `DIAGNOSIS`; new initial
decision is likewise DIAGNOSIS-only. Successful full/partial approval maps to
`AUTHORIZED`, rejection to `REJECTED`, in the one transaction above. After that,
new quote edits/decisions are refused in this online slice. Historical receipts
and detail remain readable. No reset to DIAGNOSIS, automatic re-consent or new
state is added.

The stage-3 activation dependency is a separately reviewable guard patch covering
**every** reachable order mutation ingress and order-linked inventory mutation
ingress. In particular, the HTTP transition route and existing `service_order`
sync update consumer both call the state machine today; both require the guard.
A quote-aware guard on that existing sync consumer does not widen its entity
union or provide offline quote support. Preserve queued conflicting mutations
for explicit resolution, never discard or silently transform them. It uses the same organization/order serialization as
first enrollment and a fresh lineage-existence check, so an old-route operation
cannot race past enrollment. Its minimum fail-closed policy is:

- For quote-managed orders, generic `authorize`/`reject` are refused; only the
  atomic quote service may consume the newly minted fresh initial plan.
- Generic execution/progression (`start_work`, `request_parts`, `resume_work`,
  `mark_ready`, `close`) is refused for quote-managed orders in this slice.
  Current order action DTOs do not identify approved line coverage.
- New order-linked inventory movements, including ADJUST, are refused for
  quote-managed orders.
  Current movement DTOs identify order/product but no exact quote revision/line;
  they cannot prove coverage or prevent spending a partial approval twice.
- Cancellation may retain the existing legal state-machine behavior and normal
  event; it does not delete consent or infer stock release. No-lineage orders
  retain all existing behavior. Existing command receipts are handled before
  new-action fences, subject to their current authority and proof rules.

All inventory-side lookup orders must remain compatible with organization →
actor → order → lineage → product when composed; do not lock product then request
an order lock. The first conservative enrollment rule means a newly managed
order has no prior hold to finalize. If a managed order somehow has pre-existing
stock effects, fail closed and require the deferred reconciliation path, not a
new RELEASE/CONSUME interpretation. Preserve existing full-hold finalization,
CONSUME plus negative ADJUST pair and idempotent receipt semantics for legacy
orders; approval itself never changes stock. Unlinked ADJUST remains an audited
legacy stock correction, not a quote fulfillment claim or a substitute for the
deferred line-coverage workflow.

**No mixed old server writers at enrollment:** before the first real lineage is
created, drain/replace every API, maintenance and business writer with the
quote-aware guarded version. An older protocol-1 binary can still acquire the
organization lock and then perform an unfenced mutation; serialization and floor
1 do not make that binary quote-aware. Require verified schema-compatible writer
rollout, backup/restore and recovery checks under separate operator authority.
Do not activate through migration/startup, silently raise protocol floors or
reintroduce an older unfenced writer against an enrolled dataset. Existing old
clients may still use the new guarded server; conflicting queued actions retain
explicit resolution rather than becoming a bypass.

This fence intentionally delivers durable initial consent without operational
execution. Enabling work, per-line reservations, quantity budgets, post-initial
corrections/revisions, cancellation with holds or re-consent requires its own
reviewed integration. Do not enable quote mutations first and defer the fence,
or mark the complete quote lifecycle ready because its initial routes pass. [S9]

## 8. Required evidence and remaining decisions

All rows below are **planned acceptance tests, not executed evidence** for this
proposal. Existing 243 quote tests (including the unchanged original 106) remain
regression requirements, not proof of persistence, fresh grants or concurrency.

| Risk                     | Required proving cases                                                                                                                                                                                                                                                                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Migration/retention      | Fresh database and 0011→next upgrade preserve unrelated rows; registry/head correct; real PostgreSQL composite FKs/append-only triggers/RESTRICT; destructive downgrade refuses before effects.                                                                                                                                                      |
| Financial reconstruction | All line kinds, stable/retired IDs, exact whole/subset totals, zero prices, discount ties/tax rounding, current corrections/withdrawals; corrupt proof, missing ancestors, branch, foreign references, wrong head/ordinal or computed money fail closed.                                                                                             |
| Races/CAS                | Two real PostgreSQL sessions: first create, revision vs decision, same ID same/different proof, competing initial decisions, correction branches in repository tests. One winner/effect set; no SQLite concurrency claim.                                                                                                                            |
| Authority                | Revoke/deactivate/scope/session change while blocked; token × initial-account × post-wait-account narrowing; expiry before commit; cross-tenant/location/order reads and retries; protocol/incarnation denial.                                                                                                                                       |
| Compatibility            | Exact legacy wildcard, BUSINESS_CAPABILITIES, v1 bundles/aliases and old stored/token snapshots unchanged; current Owner explicit addition only; TechnicalAdmin empty; no migration/startup adoption; explicit adoption version/audit/revocation; old client unknown-grant handling and unchanged policy parser.                                     |
| Semantic replay          | Reordered selection/targets and equivalent UTC offsets replay; changed evidence/actor/order CAS or revision presentation order conflicts; retry after new head, replacement/withdrawal, state transition and cancellation returns old receipt plus fresh projection, no new effects.                                                                 |
| Atomic effects           | Inject failure at revision/decision, receipt, head CAS, order event, change feed and each outbox insert; complete rollback. Lost response after commit recovers exact original IDs/time, with effect counts unchanged.                                                                                                                               |
| Bounds/DTOs              | MAX and MAX+1, bool/float/exponent/string, signed discount outputs, multiplication overflow and safe computed result; duplicate keys, invalid UTF-8, chunked oversize, excessive depth/edges/text/history; maximum fixture under unchanged timeouts; exact TS round trip, bounded errors and private headers on both route families.                 |
| Enrollment/bypass        | Concurrent creation vs old order transition/inventory/sync entry, scope and initial-state checks, any prior stock-history refusal, partial approval cannot start generic work or stock, legal cancellation preserves evidence, no-lineage legacy regressions unchanged; mixed-old-server admission remains an explicit blocked rollout prerequisite. |
| Restore                  | Real PostgreSQL backup/restore into a clean instance preserves canonical histories/proofs/receipts/effect IDs; strict reconstruction matches before/after; incarnation rotation rejects old tokens and checkpoint reuse; retry with fresh admission emits nothing. No restore claim from backup creation alone.                                      |

Before stage 3, review must specifically confirm every reachable mutation ingress
in the fence, quote-only adoption compatibility, the chosen capacity fixtures and
the fresh-authority transaction. These are implementation acceptance gates, not
an invitation to broaden Tasks 6/8. No unresolved choice in this proposal should
be silently filled by widening roles, accepting coercion, truncating histories
or treating state-only approval as line authorization.

### Source map

Paths below are relative to the inspected checkout; platform paths share
`services/platform/src/cycling_workshop/`.

- **S1:** `docs/superpowers/plans/2026-09-01-v0.2-increment-2-budgets-inventory.md`, Tasks 5–11; `services/platform/migrations/versions/0011_workshop_branding.py`; `apps/web/src/access-kernel/database.ts:73`.
- **S2:** `quotes/history.py`, `quotes/decisions.py:450–588`, `quotes/domain.py:194–290`; `service_orders/models.py:20–96`; `inventory/models.py`; `db/registry.py`.
- **S3:** `sync/writes.py:20–52`; `identity/context.py:55–81`; `identity/cutover.py:29–108`; `identity/administration.py:67–110`.
- **S4:** accepted decision ADR §§4/6/7; `quotes/decisions.py:542–588`; `sync/proof.py` (raw proof contrast).
- **S5:** `identity/roles.py:8–99`; `identity/admin_schemas.py:38–52`; `identity/admin_router.py:52–68`; `identity/administration.py:127–141,198–283`; `identity/branding_cli.py:43–83`; `identity/admin_cli.py:31–99`; `cli.py:56–110`; [branding compatibility clarification](2026-10-14-shared-workshop-branding.md#compatible-authority-and-catalog-contract); earlier [authenticated-context ADR](2026-10-14-authenticated-offline-context.md); `apps/web/src/access-kernel/server-context.ts:94–115`.
- **S6:** accepted arithmetic ADR §§1–3 and `quotes/domain.py`; accepted decision ADR §5; `sync/baseline_schemas.py:73` (safe version precedent).
- **S7:** `branding/http.py:18–51`; `branding/schemas.py`; `api/errors.py:22–45`; `api/middleware.py:36–45`; `app.py:79–117`.
- **S8:** `service_orders/models.py:65–96`; `service_orders/repository.py:50–89`; `sync/writes.py:55–90`; `identity/audit.py:25–60`; `events/outbox.py:11–39`; `events/models.py:11–27`.
- **S9:** accepted decision ADR §§7.2/7.3/8; `service_orders/domain.py:37–52`; `service_orders/router.py:129–173`; `inventory/schemas.py`, `inventory/service.py`, `inventory/repository.py:144–156`; `sync/service.py:196–228,486–525`; committed [pure-domain limitations](../10-spec-development/2026-10-15-quote-decision-domain.md).
