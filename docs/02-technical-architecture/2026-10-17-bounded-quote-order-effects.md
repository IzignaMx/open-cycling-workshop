# ADR amendment candidate: bounded quote-linked order effects

Status: accepted direction for synthetic development; joint implementation and operational qualification pending. This amendment selects bounded full-integrity order effects without enabling service routes or commands. Earlier schema preparation was static-reviewed only; the distinct schema-0012 service result below does not qualify this amendment.

## Explicit test-dialect accommodation

The active V0.1 implementation plan assigns PostgreSQL to production and SQLite only as a functional unit-test surrogate. Migration 0013 therefore proposes PostgreSQL 18 GENERATED ALWAYS STORED byte counts and SQLite VIRTUAL counts using length(CAST(payload AS BLOB)), with UTF-8 encoding required. SQLite is excluded from database-memory/prefetch, PostgreSQL locking/concurrency and migration/restore qualification. This avoids rebuilding referenced generic tables solely for surrogate support.

Migration 0013 conservatively refuses ANY populated old effect tuple before DDL under its held transaction/locks, without backfill or NOT VALID acceptance. PostgreSQL's table rewrite/ACCESS EXCLUSIVE locks and generation during writes/restore require separately qualified operational budgets. SQLite's zero-row version-table DML transaction bridge, exact upgrade and DDL rollback are proposed, not runtime-proven.

The joint candidate combines metadata/schema with the existing full effect reconstruction, bounded reader and admission validator. Do not replace effect reconstruction with the older schema-only blanket rejection. Joint candidate tests, imports, collection, lint and compilation remain unexecuted at this preparation checkpoint.

## Full integrity decision and acceptance

### Decision: bounded new quote-linked order effects

2026-10-17. Architecture direction accepted for local synthetic preparation. Joint source authoring is in progress; its verification and installation remain separately gated.

## 1. Selected three-column design, pending implementation and migration evidence

Keep complete historical order payload validation and full canonical
change/outbox equality on every quote reconstruction, including exact replay
and restore. Add an explicit admission envelope only for newly created
quote-linked order effects. Retain every existing generic order, Text field,
change and outbox unchanged. Reject an ineligible new enrollment before any
lineage/write; never truncate or move an already enrolled order back to legacy.

Use the existing actual event/change/outbox rows. Add one nullable immutable
`order_effect_version` scalar to the receipt plus one database-generated STORED
raw-byte count to each generic change/outbox table. Do not introduce a payload
witness, digest, application-maintained trust cache, summary table or replacement
event framework. Version 1
selects the new effect contract, not proof that its source rows remain valid.
Every source row is still revalidated. Keep semantic command proof version 1.

This is a narrow ADR amendment: the new admission envelope, persisted effect
version, generated-count migration, explicit validation owner and unsupported-history policy are accepted for synthetic joint preparation. It is not an interpretation that the existing financial byte limits
already apply to generic payloads. A reduced projection is not selected.

This choice satisfies the design requirement for bounded PostgreSQL and Python
quote prefetch under ordinary SQL mutations, while retaining every full-integrity
check. It does not establish execution evidence, protect against physical damage
to generated metadata, or close migration/write/restore/cancellation gates. The
two additional columns retain separately contained migration/restore qualification; the existing six-case synthetic batch cannot qualify them.
The smaller query-time-cast design is not selected for this requirement.

## 2. Evidence and precise compatibility baseline

The last reconciled integrated-main baseline was `8a7eeecc39b0a43097484d10dc30af541ae38156`, whose
reconstruction supports quote-only receipts. The development candidate has
additional complete effect reconstruction and a private service, but no mounted
quote routes. Neither source establishes the contents of a real installation.

The immediate joint-development base is commit
`9c07e2249fedd59462e00d9a1b44652709b05e2e`, tree
`fe30964b9b164b4eaf1d63449f46c490de548f2e`.
[Run 39053813148](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39053813148)
passed two DTO and four sequential service cases with PostgreSQL 18.4,
psycopg 3.3.4 and four isolated revision-0012 schemas. This narrow result does
not cover migration 0013, bounded payloads, concurrency, restore or capacity.
The response-failure case has no explicit callback-reached sentinel; the
expired-deadline case refuses before its writer. The new fake-result regression
was not selected. The earlier failed run 39053071575 remains preserved; its exact exception was
not retained, although a concrete Result-conversion defect was subsequently
corrected.

- Existing generic order Text is unbounded; HTTP intake bounds do not cover
  every writer or historical/restored row. Its flat sync projection has 14 fields.
- The baseline quote loader fetched whole mapped order and linked JSON rows.
  This amendment requires bounded scalar/CASE loaders before decoding instead.
- Complete effect reconstruction is retained, including full canonical equality
  of generic order change/outbox payloads, actual event identities and financial
  history. The new version does not substitute for those checks.

## 3. New limits, independent of financial history limits

For effect contract 1 select these inclusive byte ceilings:

| Boundary | New limit and meaning |
| --- | --- |
| Current-order source prefetch | Sum of UTF-8 bytes of reported_problem, intake_condition, accessories, priority and diagnosis, counting SQL null as zero, at most 262,144 bytes. Metadata is separately bounded before text fetch. |
| One retained order projection | At most 262,144 canonical UTF-8 JSON bytes, after full closed-shape validation. Both the change and order-outbox payload must satisfy this. |
| One stored raw JSON representation | At most 1,048,576 UTF-8 bytes before application JSON decoding. Both stored copies must satisfy this independently. |
| Linked initial transitions per lineage | Zero or one. Enforce in reconstruction, not merely the current writer. A linked initial proof must have expected decision sequence 0. |
| Aggregate linked generic content | At most 524,288 canonical bytes and 2,097,152 raw transfer bytes, since there is at most one pair. These are additional to the existing 16 MiB financial/evidence budget. |

Rationale: reuse the already reviewable 256 KiB unit and 1 MiB transport scale as
new explicit application admission choices. The current HTTP intake maxima total
10,030 codepoints before IDs/times and diagnosis; worst-case ASCII escaping of those
characters uses at most 120,360 bytes, excluding diagnosis and metadata. This leaves substantial room without claiming all
legacy or sync-origin orders fit. No measured latency or memory sufficiency is
inferred from those numbers.

Raw and canonical limits are conjunctive, not interchangeable. Whitespace and
Unicode escaping can inflate stored JSON. A conservative encoded upper bound
for a prefetched source is `6*S + 8192`, where S is the five-field UTF-8 sum;
8192 reserves the fixed 14 keys/punctuation, up to five bounded 36-codepoint IDs,
state, nullable values, two bounded UTC timestamps and safe integer digits.
With S at its ceiling this bound is 1,581,056 bytes. It is a finite allocation
ceiling, not the exact canonical size and not proof of the 1 MiB raw limit.
Measure both exact encodings after bounded hydration; a candidate that fails
either is refused. Do not promise that canonical <=256 KiB implies every legal
raw spelling <=1 MiB. No boolean, arbitrary numeric exponent or nested value is
valid in this 14-field shape; malformed input is rejected rather than budgeted
as an alternative valid encoding. Exact threshold/UTF-8 fixtures must prove the
envelope arithmetic before implementation is accepted.

## 4. First command: lock scalars, bound source, then hydrate

1. Preserve organization → fresh actor → order → lineage lock ordering, the
   narrowed incoming principal intersection, scope, protocol/incarnation and
   expiry rules. Require PostgreSQL server/client encoding UTF8 for this
   production boundary; do not silently use character counts as UTF-8 bytes.
2. Acquire the scoped order row lock through an explicit bounded scalar column
   selection: IDs/customer/bicycle, state, version, creation/update times. Do
   not select the mapped `ServiceOrderRecord`, create its domain object, invoke
   its serializer, or permit lazy-loading of Text yet. Refresh after a wait.
   Current quote response/replay needs only its existing closed scalar DTO.
   Exact prehydration metadata domains: existing IDs are 1..36 codepoints and
   at most 144 UTF-8 bytes, nonblank with no whitespace/NUL/surrogates; bicycle
   ID alone may be null. State is one of the finite existing OrderState literals
   and at most 30 ASCII characters. Version is an exact positive integer within
   the actual SQL INTEGER range (1..2,147,483,647); an initial transition also
   requires version <2,147,483,647. Times must be finite Python-representable
   UTC instants (year 1..9999, microsecond precision), never PostgreSQL infinity;
   their existing UTC ISO spelling is at most 32 ASCII bytes. Reject malformed
   metadata before Text hydration, without silently coercing or repairing it.
   SQL CASE predicates reject nonfinite or out-of-year-1..9999 timestamps before
   the driver attempts datetime conversion.
3. Lock/load the lineage and perform the existing receipt lookup and complete
   reconstruction. Exact replay returns before NEW-command size/enrollment
   eligibility checks. Quote-only history never reads current order Text or
   unrelated legacy change/outbox payloads merely to return a quote receipt.
4. For NEW first enrollment, after ordinary state/version/inventory/history
   checks, select only individual `octet_length` scalars of the five columns,
   coalescing their LENGTH results to zero for nullable values. Cast each length
   to BIGINT before summation/multiplication. Keep the same row lock and session.
   No concatenation, JSON constructor, `convert_to`, normalization, character
   scan or `SELECT *` occurs before these checks. If S exceeds its ceiling,
   reject before lineage creation or any durable effect.
5. Fetch the five fields only behind an explicit CASE guard using their current
   length predicates, in the same locked transaction. Each CASE must return SQL
   null on failure; return an independent admission boolean to distinguish it
   from genuine null field values. No ORM auto-decoder/lazy load may bypass it.
   Recheck returned bytes in the application. The lock prevents normal writers
   changing the order between measurement and use; the guarded fetch is also
   checked on the actual returned row. Review generated SQL, not just ORM intent.
6. Validate the full source and exact hypothetical transition projection before
   enrollment. Use the longest allowed target state and bounded worst-case
   version/timestamp spelling for an enrollment eligibility check; label that
   conservative check honestly. For a NEW initial decision, repeat the scalar
   preflight and validate the exact actual target/version/time before any write.
   A prior enrollment check is not permanent permission to skip this recheck.
7. After the fresh domain decision and transition plan are validated, write the
   actual order event/version, generic change and order outbox, quote outbox,
   history/cursor and versioned receipt in the single owning transaction. Encode
   and check both actual raw generic payload representations before database
   submission, then validate the inserted retained sources before receipt/commit.
   Prepare and measure the exact immutable raw JSON string before any write.
   Submit that retained string as an explicitly Text-typed bind cast to JSON
   on PostgreSQL, and as bare Text on SQLite, for both copies. Do not pass it
   through the ordinary dictionary JSON adapter or reserialize it. Verify
   retained text and generated counts after insertion.
   Failure at any stage rolls everything back under the existing rules.

An oversized not-yet-enrolled legacy order receives fixed `409 quote_conflict`
with the existing closed message; internal diagnostics may use only the fixed
category `order_effect_payload_limit`. Its lineage and all data remain unchanged,
and its existing legacy management remains available. The accompanying UI should
explain that online quote enrollment cannot handle this order's retained content
and that the order was left unchanged. It must not recommend deleting/trimming
evidence, silently make another order or fabricate an export workaround.

For an already quote-managed order, the same new-command refusal preserves all
fences and existing quote reads/replays. Never remove enrollment or offer a
legacy authorization bypass. Larger-content support is a later reviewed contract
change. Revision-only operations do not invent order effects or rewrite text.

## 5. Historical raw JSON prefetch: generated-count guard before any cast

Load the one linked event/change/order-outbox association through scoped joins
and one consistent statement snapshot. Return bounded metadata, `note IS NULL`,
the actual STORED counts specified in §5.1, and CASE-guarded payload text only
when BOTH counts are in 1..1,048,576. Do not compute raw JSON lengths by casting
payloads in this read query. Both payload casts/values must be behind the stored
scalar guard; an unguarded duplicate SELECT item or ORM JSON decoder defeats it.
The source identities remain the actual receipt-linked rows, not a lookup by
time/payload. A global cursor independently matches the complete admitted scope.

Ordinary `octet_length(payload::text)` is sufficient to gate transfer to Python
and ordinary driver JSON decoding only. It is NOT a pre-detoast database-memory
bound. PostgreSQL 18's text length implementation reads the TOAST raw-size header;
however JSON-to-text has I/O coercion, and json_out detoasts/materializes first.
`pg_column_size` can describe compressed size and is not an equivalent guard.
These facts were checked in primary upstream source, not by running a database.

Therefore query-time length casting is rejected as the production preflight.
The selected generated-count design makes these distinct claims:

- Current-order Text preflight rejects before full Text materialization using
  metadata-only lengths. STORED-count historical preflight rejects oversized
  ordinary SQL rows before JSON cast/materialization. Both claims require exact
  PostgreSQL/driver/query-plan evidence before implementation success is claimed.
- New quote writes are already bounded before SQL. Derived counts are generated
  during writes and logical restore, not during quote prefetch. Existing generic
  legacy writes keep their prior content contract; they are not made bounded by
  this design. Migration and generic write/restore resource costs remain real.
- This proposal does NOT establish a general database-memory or total-Python
  wall-cutoff guarantee. The narrower read guarantee assumes ordinary SQL storage
  invariants and verified schema, not physically damaged counts or privileged
  schema replacement. Full content validation still always follows prefetch.

Do not add a privileged `LANGUAGE internal` alias, custom binary extension, global
JSON cast, generic JSON-to-Text migration or storage-compression change in this
slice. An internal alias could exploit the current text representation, but would
add privileged installation and version/ABI/security obligations. That requires
a separate reviewed architecture decision; it is not an ordinary implementation
detail or an authorized workaround.

Primary sources: [PostgreSQL 18 string functions](https://www.postgresql.org/docs/18/functions-string.html),
[textoctetlen](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/adt/varlena.c#L689-L701),
[TOAST raw versus physical size](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/access/common/detoast.c#L503-L607),
[JSON representation/output](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/utils/adt/json.c#L95-L123),
[cast catalogue](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/include/catalog/pg_cast.dat#L434-L441),
[internal-function aliases](https://www.postgresql.org/docs/18/xfunc-internal.html).
The branch sources are inspected references, not a substitute for pinning the
exact PostgreSQL image/source digest in qualification.

### 5.1 Exact selected generated-column amendment and operational cost

To meet bounded PostgreSQL JSON prefetch under ordinary SQL mutations, add two
generated STORED counts, in addition to the receipt version. Proposed DDL for
review only; this document executes none of it:

```sql
ALTER TABLE sync_changes ADD COLUMN order_payload_raw_octets bigint
GENERATED ALWAYS AS (
  CASE WHEN entity_type = 'service_order'
       THEN octet_length(payload::text)::bigint ELSE NULL END
) STORED;

ALTER TABLE outbox_events ADD COLUMN order_payload_raw_octets bigint
GENERATED ALWAYS AS (
  CASE WHEN aggregate_type = 'service_order'
       THEN octet_length(payload::text)::bigint ELSE NULL END
) STORED;
```

Require UTF8 server/client encoding. These are exact retained-JSON text bytes,
not canonical bytes. Ordinary payload writes atomically regenerate the count;
an independently supplied count is forbidden by PostgreSQL. On a quote read,
select the STORED scalars and guard BOTH actual payload casts with both counts
in 1..1,048,576, in the same scoped statement snapshot. Null/invalid/unknown
metadata fails closed. Compare fetched raw length to the count and still perform
every full shape/canonical/content check. A generated count is retrieval metadata,
never a proof replacement. Verify catalog `attgenerated='s'` and the exact
expression before enabling this loader; do not accept a mutable ordinary column.

PostgreSQL requires immutable generation expressions and defaults new generated
columns to VIRTUAL, so STORED is intentional. Its source catalogue marks
json_out/textin/octet_length immutable (including the catalogue default); that
supports the expression but is not an executed DDL result. SQLAlchemy uses
Computed(expression, persisted=True), with no application default or supplied
count. [PostgreSQL generated columns](https://www.postgresql.org/docs/18/ddl-generated-columns.html),
[function catalogue](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/include/catalog/pg_proc.dat),
[catalogue defaults](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/include/catalog/pg_proc.h#L68-L72),
[SQLAlchemy Computed](https://docs.sqlalchemy.org/en/20/core/defaults.html#computed-columns-generated-always-as).

Cost: adding STORED columns rewrites both complete generic tables and their
indexes, with ACCESS EXCLUSIVE locking. The conditional expression avoids
calculating unrelated entity payload lengths, but does not avoid their table
rewrite. No legacy payload is truncated, normalized or subjected to a new size
CHECK; oversized order payloads retain a large count. Migration needs verified
backup/isolated restore, drained writers and separately approved duration,
storage/WAL, containment and cleanup envelopes. [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/18/sql-altertable.html).

Generation still materializes JSON at migration/write/logical-restore time.
New quote writes have the pre-SQL bounds above; generic legacy writes remain
outside this new admission contract. Outbox bookkeeping write overhead also
requires measurement. Logical restore recreates expressions and loads base
columns so the database recomputes counts; COPY excludes generated columns by
default, but the project's exact dump/restore procedure must prove this. Never
skip an oversized legacy row on generation failure. [PostgreSQL COPY](https://www.postgresql.org/docs/18/sql-copy.html).

This design closes ordinary-SQL steady-state JSON prefetch, not privileged
schema changes, damaged physical generated metadata, migration/write memory or
total-Python cutoff. Physical restores require independently contained corruption
validation; no count establishes content integrity. SQLite functional/schema
support needs explicit dialect handling and forward-migration evidence, not a
mutable-counter emulation presented as the PostgreSQL guarantee.

Decision: the three-column architecture and scope are accepted for synthetic
joint preparation. It widens generic schema/write/restore and installation scope,
which the initial finite service batch does not qualify. Local joint implementation
is permitted; installation, migration/restore qualification and production
exposure remain gated.

## 6. Exact validation ownership and corruption semantics

Put the finite generic order projection validator in the order/sync module,
e.g. `sync/order_projection_integrity.py`; quote reconstruction MUST invoke it.
This is one typed order projection validator, not a generic event framework.
It owns all 14 fields, required versus nullable strings/IDs, strict UTF-8/JSON,
canonical UTC timestamp spelling, positive exact version, exact closed shape,
both byte envelopes, and full canonical equality of change and outbox. No omitted
generic field is delegated to an unspecified future checker. It is invoked on
new quote-effect admission, every quote reconstruction/read/replay, and restore.
Unrelated generic-order records keep their prior contracts and retention.

Fetch raw JSON as text. Before json.loads or any ordinary JSON decoder, check
raw type/count/UTF-8 byte bounds and perform a string/escape-aware scan of depth
and numeric lexemes. Reject malformed Unicode/NUL/surrogates, nonfinite or
fraction/exponent values, excessive integer lexemes and depth >12. Duplicate-key
rejection during decoding and exact 14-field/domain validation complete acceptance.
This closes additional raw-codec ambiguities; it is stronger than merely testing
the candidate's already ORM-decoded dictionaries. Preserve text exactly without
normalization and use the existing quote canonical JSON rule for equality.

The quote module owns and checks all of these in addition:

- Complete canonical command/proof/result/history/financial/evidence chain.
- Complete receipt tuple plus effect version 1; resulting order version equals
  expected +1 and is representable by the actual order-version SQL column.
- At most one populated tuple; initial mode, sequence precondition 0, eligible
  customer evidence and fresh planner semantics. APPROVE/PARTIAL map to
  authorize/AUTHORIZED; REJECT maps to reject/REJECTED.
- Event identity equals operation/decision ID, matching order/organization,
  DIAGNOSIS source, action/target, actor, time and null note.
- Change cursor, tenant/location/order/entity/update/version/time, plus historical
  payload IDs/customer/target/version/update time and creation <= event time.
- Order outbox actual delivery ID, scoped aggregate/type/event/time, plus complete
  payload validation/equality. Quote outbox is independently allocated and fully
  validated; quote/order delivery IDs differ.
- One-to-one ownership and no missing, duplicate, foreign, shared, partial or
  extra association. Mutable attempts/published_at never establish integrity or
  invalidate an otherwise valid historical receipt.

Stored version-1 oversize or malformed content is `500 quote_integrity_failed`;
the old unversioned populated tuple stays unsupported and also fails closed.
An interrupted length check whose result is unknown is availability failure,
not a proven corruption verdict. Fresh authority is required even for replay;
after commit-attempt uncertainty retain the original operation ID and current
outcome-unknown rules. A newer/cancelled current order never replaces historical
source validation. Full validation proves consistency, not immunity to a
privileged operator consistently rewriting all evidence.

## 7. Additive migration, old data and restore

After rechecking the actual schema head, use one new forward migration after
0012; never edit 0012. Add nullable small integer `order_effect_version`, no
default and no effect-version backfill. Include the exact two generated STORED
columns in §5.1; existing count generation/table rewrite is explicit migration
work, not a metadata-only change or permission to rewrite payload values. Keep
all existing retention constraints/triggers. If the separately approved migration
envelope cannot be met, stop and preserve the source database and backup rather
than silently converting a generated count to a mutable column.
Define the complete new receipt check:

- All four order-effect fields null AND effect version null: valid quote-only.
- All four present AND effect version exactly 1 AND kind decision: eligible for
  full application-effect reconstruction.
- Every other combination, including full tuple/version null, fails closed.

Existing immutable receipt guards cover the added scalar. Unknown version values
fail, including on restore. No version may be inferred from IDs, fitting bytes,
domain mode, current order state or a currently valid hash. Proof bytes and
receipt IDs never change. The existing external Effects DTO can retain its exact
union; the storage version is internal, so do not accidentally add an unreviewed
wire field or new proof input.

Before validated enforcement or activation, perform metadata-only inventory of
existing populated tuples under the separately authorized migration procedure.
On the supported all-null case, validate the new constraint. If any old populated
tuple exists, preserve it and stop activation; it was already rejected by main's
reconstructor. Do not assign version 1. The selected migration refuses before DDL when any old populated tuple exists; it does not leave a NOT VALID constraint or invent a version. Exact migration/restore tests must cover this refusal and preservation. No actual installation inventory is claimed here.

Restore retains all original order/change/outbox JSON bytes, financial evidence,
effect version and IDs. For logical restore recreate the generated definitions
and restore base values so PostgreSQL recomputes their counts; do not trust an
imported counter. Physical restore needs its separate contained corruption
qualification before the prefetch guarantee is asserted. In a clean isolated
target, run the generic validator for
every quote-linked pair and complete quote reconstruction before reopening that
boundary; stop on corruption/unsupported tuples rather than repair them. Then
rotate incarnation according to the accepted recovery procedure and prove fresh
same-ID replay returns the old receipt with unchanged effect counts. Historical
quote-only initial decisions remain null and never acquire an order transition.
No restore enqueues/republishes a command or regenerates identities. Existing
unrelated oversized legacy orders survive restore unchanged and are not declared
corrupt by this new quote-only envelope.

## 8. Acceptance and next bounded work

Complete functional acceptance requires additive receipt-version and generated-count schema/model, scalar order loading, guarded linked raw loader, finite generic validator, unchanged complete quote checks and new-admission refusal behavior. The joint candidate composes the schema, bounded loaders, raw write seam and full reconstruction against commit `9c07e2249fedd59462e00d9a1b44652709b05e2e`. Source authoring is in progress; exact-source review and contained execution remain pending. Preserve the frozen amendment and consumed service source/workflows/evidence. Earlier six-case PG0012 evidence does not qualify this joint design. An inert limit constant or witness-only intermediate cannot qualify the full feature.

Finite future evidence, with tiny injected thresholds before any production-size
specimen, must establish:

1. Each accepted/rejected boundary at N-1/N/N+1 for source, exact canonical and raw
   bytes; ASCII control escaping, quotes/backslashes, multibyte/supplementary
   Unicode, nullable fields, maximum metadata and timestamp/version growth.
2. An oversized legacy order fails new enrollment with no lineage/effects and
   remains usable through its old paths. Existing managed orders never lose
   fences. Exact historical null replay never fetches their current Text.
3. Actual SQL selects no unguarded Text/JSON, including implicit ORM/lazy loading;
   source measurement/fetch/write share locks; change/outbox snapshot is coherent.
   Real PostgreSQL compressed/external Text and compressed JSON demonstrate the
   distinct preflight guarantees without an unbounded/stress fixture. A tiny
   ordinary SQL payload update must regenerate its count and oversized refusal
   must not evaluate the guarded payload cast; confirm the STORED catalogue and
   the exact immutable expression. No driver eager JSON decoding is allowed.
4. Full canonical mismatch in any generic field, unknown/missing keys, malformed
   unselected fields, wrong bool/int/null/time and raw duplicate/exponent cases
   fail. A hash/reference alone never supplies the expected success result.
5. Complete APPROVE/PARTIAL/REJECT effects, all tuple/version combinations,
   one-versus-two transition tuples, foreign/shared cursors and outboxes, advanced
   current order, disabled new commands, revoked authority and old null receipts.
6. Rollback at every write/effect/serialization point; lost commit acknowledgement
   resolved by fresh exact replay without duplicated effects.
7. Empty/all-null forward migration, preserved unsupported populated legacy rows,
   immutable version, restore with bad generic payload/oversize/unknown version,
   generated-count recomputation and immutable-expression schema verification,
   incarnation rotation and unchanged effect identities/counts. Preserve unrelated
   oversized legacy data and prove outbox bookkeeping behavior/cost separately.

First qualification proves only its named finite cases. Maximum financial
history, generic-envelope capacity, real PostgreSQL atomicity/restore, application
cancellation, every ingress fence, API/UI and physical/operator gates remain
separate. Preserve failed profiles 51/56; no rerun, increased budget, speedup,
hard cutoff or activation claim follows from this design.

## 9. Selected joint implementation seams

One private immutable prepared projection holds the exact validated flat payload,
canonical UTF-8 bytes, raw JSON string and measured raw UTF-8 byte count.
Raw type/count/UTF-8 bounds and string/escape-aware depth/numeric lexical checks
precede json.loads; duplicate-key rejection and full domain validation then
complete decoding. Preserve every valid string.

The quote-linked append path submits the same measured raw string as a Text bind
cast to JSON on PostgreSQL, and as raw Text storage on SQLite. It must not run a
second JSON serialization through the ordinary dictionary adapter. Reuse existing
outbox IDs, metadata, cursor and transaction semantics; generic writers retain
their existing dictionary-based contracts.

First enrollment admission belongs to the common new-Create repository path,
after exact replay resolution and before any write, independent of application
callbacks. Prepare a new initial transition and its full encoded projection
before begin_nested(), which can itself flush. Persist via scoped scalar CAS;
never fall back to a full mapped order fetch through generic save().

Before count-gated loads, verify the actual resolved PostgreSQL table OIDs,
ordinary non-inherited/non-partitioned tables, payload JSON rather than JSONB,
generated STORED BIGINT counts and the complete finite accepted pg_get_expr
representation. Reject unsupported inheritance/partitioning rather than traverse it. Do not trust expression substrings or a persistent metadata cache.
Both raw payload casts share the conjunction of both count bounds in one scoped
statement. Fetch note nullness rather than note Text, recheck actual UTF-8 byte
counts, and validate both complete retained projections. The SQLite check proves
only its explicit VIRTUAL surrogate definition.

Version 1 is written only for a complete newly prepared bounded initial effect.
Historical all-null receipts remain null and replay without a transition.
Unknown, partial, unversioned populated or invalid-version tuples fail closed
before raw payload fetch. Migration0013 refuses pre-existing populated 0012
receipts before DDL, rather than assigning provenance retrospectively.

Acceptance must separately demonstrate genuine valid quote-only 0012 history
migrated to 0013 and replayed in a fresh session. Toy migration payload preservation
alone is insufficient. DDL rollback and logical restore remain distinct,
contained operational qualifications; source tests do not mark them complete.
