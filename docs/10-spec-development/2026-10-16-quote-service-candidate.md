# Internal quote service candidate: historical preparation

## Current reconciliation update · 2026-10-17

The original preparation below remains an unexecuted historical source record.
Its 12 Python source/test files have now been copied byte-for-byte onto the
current-main tree plus the exact published containment guard. Bootstrap run
[39007201961](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39007201961)
qualified 34 finite guard cases inside the independent actual containment venue,
with both cleanup receipts verified. It did not run this service or DTO code.
The reconciled service package and exact six-node initial qualification remain
pending independent review and separately authorized publication. Schema 0012
is retained; schema 0013 is excluded. The [current qualification scope](2026-10-17-quote-service-six-case-candidate.md)
records the source and evidence boundaries. All original behavioral, deadline,
coverage and exposure limitations below remain open.

## Original status and scope

Prepared from qualified PR57 tree `540d963d686dd30bda31e7382b15837eae2c9c44`.
This is an unmounted synthetic candidate, not a verified implementation or an
activation decision. The coordinator accepted the reviewed functional plan and
ADR addendum as synthetic development direction on 2026-10-16. The addendum's
source-bound hash is `964a19e02f7b52c95d13fbdbf0e906574c7568cc1d5dbb4eb685a063dac6ae23`.

The finite candidate connects internal create/revise/initial-consent commands to
fresh authority, a transaction-owned immutable receipt, real order effects and a
closed command response. It deliberately does not mount routes, adopt grants,
change accounts/settings, add UI or activate enrollment. HTTP/sync/inventory
ingress fences, runtime transport/TS contracts and UI remain required parts of
the same cohesive slice before exposure. This is not an independent Deadline
framework or a new capacity/profile experiment.

## Transaction boundary

- The service requires a dedicated clean Session and owns the outer transaction.
  It rejects an existing transaction or unrelated pending changes without taking
  ownership of them. Writer admission holds organization and fresh actor locks;
  repository acquisition continues with order and lineage locks.
- Both the incoming authority snapshot and freshly locked effective grants must
  contain the operation's explicit quote/order capabilities. Exact replay still
  requires all its grants, current session/incarnation/protocol and scope.
- Full reconstruction and semantic identity comparison precede new-command
  availability. The default-false internal availability value only refuses new
  commands. Exact replay does not apply new effects, including historical
  repository-only decisions whose order-effect tuple is null.
- New enrollment is DIAGNOSIS-only and uses authoritative EXISTS for any linked
  inventory movement and contradictory recorded progression under the same
  order lock. New online edits/decisions after any decision are refused.
- New consent requires initial customer evidence for the locked order, one of
  the five accepted channels, and exact full/partial/reject whole-line selection.
- The private repository composition retains the actual fresh ledger.record
  result. The transition planner's resulting sequence is checked separately from
  the incoming CAS sequence. The service creates the order event, projection
  change and order outbox in the same savepoint before the one immutable quote
  operation receipt is inserted. No later receipt UPDATE completes its effects.
- `append_change` returns its allocated cursor and outbox identity; old callers
  can ignore the typed return. Stored effect validation uses historical linked
  event/change/outbox rows, global-cursor scope and exact payload association,
  never today's mutable order state as a historical oracle.
- DTO validation and exact response serialization happen before flush/expiry
  recheck/COMMIT. Any earlier failure rolls back the outer transaction. Once
  COMMIT is sent, a missing acknowledgment remains outcome unknown even if a
  later rollback returns; a new authorized request with the same identity must
  resolve the persisted receipt.

## Compatibility

Public repository.apply remains the repository-only append API. QuoteSnapshot
keeps its fields. QuoteReceipt gains an optional order_effects field defaulting
to None; existing oracle comparisons explicitly add that null expectation while
comparing every original field. Frozen oracle source files are unchanged.

Command responses keep immutable receipt facts separate from current head,
current decision and a restricted current order projection. Historical null
effects are truthful, never inferred from a decision's mode. Closed required
fields, strict safe integers, shared identifier/time validation, discriminated
effects, exact ordinal arithmetic and distinct outbox identities are enforced.
Response revalidation protects against model_construct/model_copy bypasses.

## Deadline and execution limitations

The proposed eight-second immutable deadline is represented by cooperative
checkpoints, plus a candidate PostgreSQL18 transaction timeout and tightening
per-statement lock/statement timeouts with readback. An explicit fixture-only
SQLite path proves no SQL deadline or concurrency behavior.

There is **no demonstrated total Python cutoff**. Final domain constructors,
codecs, driver calls and ORM materialization can run between checkpoints. The
candidate also does not enforce the proposed one-second acquisition budget over
DNS/TLS/new connections/executor queues, or the two-second cleanup-only budget
over synchronous rollback. These are unresolved execution/exposure gates, not
extra allowed business time. No timeout or resource limit may be increased to
pass later checks. The unmounted service is not a production admission boundary.

Historical generic order projections introduce another unresolved resource
boundary. ServiceOrderCreateRequest limits reported_problem to4000 characters,
intake_condition to4000, accessories to2000 and priority to30. However, retained
order Text fields (including diagnosis), ServiceOrderResponse and order_payload
have no authoritative aggregate serialized-byte bound across all existing
writers/restored data. Effect reconstruction checks the closed historical payload
and exact change/outbox equality; its JSON traversal/serialization can therefore
process more data than the quote logical-record limits describe. The256KiB
record/16MiB history limits apply to quote logical records, not this legacy
projection. No new lower legacy text cap is silently introduced. Qualification
and exposure require a separately reviewed strategy for this retained-payload
resource boundary, in addition to the synchronous Python cancellation gate.

The authoring host has no verified cgroup/descendant containment. Therefore:

- Tiny service, DTO and storage-effect tests were written before implementation
  but were **not run**. Neither RED nor GREEN has been observed.
- No import, compilation, formatter, linter, typechecker, contract suite,
  PostgreSQL, browser, container or workload was executed for this candidate.
- Test modules pin SQLite where applicable and reuse tiny four-line fixtures;
  no maximum history or implicit large fixture is authorized.
- Independent review is source inspection only. Syntax, types, behavior and
  rollback remain unverified until an explicitly authorized contained venue
  passes actual preflight and executes an approved named selection.

Prepared cases include actual effect rows on first receipt insertion, exact
replay with flag off, revoked grants, historical null effects, order advancement,
foreign/shared/missing effects, response/flush/cancellation failure rollback,
commit acknowledgment loss, session ownership and closed DTO corruption.
The prepared service happy path currently uses PARTIAL. Successful APPROVE and
REJECT service cases, and enrollment refusal with existing movement/contradictory
history, remain missing coverage in this frozen candidate. Source review does
not substitute for those tests. PostgreSQL/driver/deadline tests and all toolchain
checks are also outstanding; no additional test execution is authorized here.

## Remaining gates

1. Independent exact-source review and resolution of any source findings.
2. Authorized venue with actual resource/privilege/controller/canary/cleanup
   proof; approved finite test selections, then observed RED/GREEN evidence or
   an explicitly documented alternative to historical RED reproduction.
3. Touched-scope static/contracts and real PostgreSQL atomicity/concurrency proof.
4. Complete ingress fences, HTTP/private transport, TS runtime validation and UI
   journey within the accepted cohesive slice, followed by stage3 evidence.
5. Existing maximum-history, nominal latency/contention, restore, old-writer
   rollout and operator gates. PR51 and PR56 remain failed and preserved.

No commit, publication, profile rerun, consumed workflow change, real account or
deployment action is part of this candidate preparation.
