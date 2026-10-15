# ADR · Bounded connected inventory visibility

Status: accepted after independent interface review, 2026-10-15; implementation and exact-source qualification pending.
Date: 2026-10-15. Base: main `22b32a9e29f5b9dca9d52c2e8d36ac1228047c54`.

## Decision, precedence and boundary

Deliver one finite connected-only read slice: existing catalog, selected product's
ledger-derived **available quantity**, and a bounded immutable movement history.
The [implementation matrix](../10-spec-development/2026-10-15-connected-inventory-read.md)
retains INV-R01–R10 and traces FR-INV-001 (basic subset), FR-INV-002/003/004,
FR-IAM-004/008, BR-006, SEC-002, NFR-004/007/010/014 and applicable ACC requirements.
This ADR incorporates all four mandatory independent-plan-review corrections.

Existing SQL0011, authenticated local schema7, baseline-2, grants, role aliases,
write protocol, journals, forms, personal themes and shared branding are unchanged.
No inventory local store, offline inventory promise, snapshot, write UI, command,
quote code, new migration, tenant activation or authority adoption is included.
OFF-002 and the remaining money-and-parts MVP acceptance remain open. Existing
commands and accepted consumption atomicity remain intact. No real accounts,
credentials, deployment or publication are authorized by this ADR.

## Wire contract

Existing GET `/api/v1/inventory/products` retains its exact bare ProductResponse
array, fields, location requirement, limit1..200/offset0..2147483647, existing
(name,id) database order and status semantics. UI requests 50 rows, retains one
page, uses previous/next offsets and permits an empty terminal page. Refresh
returns to offset0; do not impose browser locale ordering on this legacy list.
Existing GET `/products/{product_id}/stock` retains exactly product_id,
organization_id, location_id and integer available_quantity. Negative values
are valid; no clamp, rounding, partial-page balance or physical-stock alias.

The only additive HTTP route is GET
`/api/v1/inventory/products/{product_id}/movements?limit=50&before=CURSOR`.
limit is an integer1..100, default50. New route only: unknown/duplicate query
keys return422 without echoing values. Path IDs retain length1..36/NUL-free rules.
Existing foreign-tenant404 and wrong-location403 semantics remain.

Response is exactly `{items: [...], next_cursor: string|null}`. Every item has
exactly seven keys: movement_id, product_id, organization_id, location_id, kind,
quantity, occurred_at. kind is ADJUST|RESERVE|RELEASE|CONSUME; quantity is the
existing signed integer. The SQL projection selects those seven columns only.
Actor, order, reservation reference, note and unrelated user/customer data are
absent, including for accounts with additional grants. POST MovementResponse is
unchanged. Historical unlinked/standalone consumption is presented honestly.

Every query predicates organization, product AND the selected product's location.
Order is `(occurred_at DESC, movement_id COLLATE "C" DESC)` on PostgreSQL and
binary equivalent on SQLite. For valid Unicode scalar text, UTF-8 byte order
matches Unicode code-point order; client comparison walks code points rather
than localeCompare or UTF-16 relational order. Reject malformed lone surrogates
at this new read/cursor boundary. Existing catalog order is untouched.

New movement-read timestamps are exact UTC `YYYY-MM-DDTHH:mm:ss.ffffffZ` in
years0001..9999 with real calendar values, no leap seconds or offset variants.
Use lossless canonical string comparison, including microseconds; Date is only
for localized presentation. Do not change old product/stock/POST timestamps.
Fetch limit+1, return at most limit, and set next_cursor only if lookahead exists.
A non-null cursor requires a full page and encodes the LAST RETURNED row, never
the lookahead. Continuation rows are strictly older than the incoming tuple.
Newest/refresh resets the boundary. Inserts newer than a traversal boundary need
refresh; inserts older can appear later. This is live paging, never a snapshot.

Cursor: canonical URL-safe base64 without padding, ASCII length1..2048, decoded
UTF-8 length<=1024. JSON uses sorted keys, compact separators, UTF-8 without
unnecessary escaping; exact keys/version:

```json
{
  "before_movement_id": "move-a",
  "before_occurred_at": "2026-10-15T00:00:00.000001Z",
  "location_id": "loc-a",
  "organization_id": "org-a",
  "product_id": "product-a",
  "version": 1
}
```

Exact encoded example:

```text
eyJiZWZvcmVfbW92ZW1lbnRfaWQiOiJtb3ZlLWEiLCJiZWZvcmVfb2NjdXJyZWRfYXQiOiIyMDI2LTEwLTE1VDAwOjAwOjAwLjAwMDAwMVoiLCJsb2NhdGlvbl9pZCI6ImxvYy1hIiwib3JnYW5pemF0aW9uX2lkIjoib3JnLWEiLCJwcm9kdWN0X2lkIjoicHJvZHVjdC1hIiwidmVyc2lvbiI6MX0
```

Decoder rejects duplicate/unknown/missing fields, bool/float version, malformed or
noncanonical bytes/encoding, invalid IDs/time, scope/product mismatch with generic
422 `invalid_inventory_cursor`. IDs remain length1..36 Unicode scalar values and
NUL-free. A cursor is only a position, never an authorization credential. Client
decodes/canonicalizes it solely to check exact scope and last-returned-row boundary;
opaque token inequality alone does not establish progress.

## Transaction-owned authority and database budgets (R4)

Each of the three GET routes executes in one narrowly scoped inventory-read helper:
validate bearer with the existing token clock; transaction-local budgets; acquire
organization compatibility/incarnation lock; acquire/refetch current actor with
populate-existing; literal token/current grant intersection via effective_principal;
validate inventory.read/location; query/materialize response; recheck signed expiry;
rollback/end transaction. Hold the barrier through response materialization, then
release every lock. No writer admission primitive, commit, business mutation, audit,
receipt, outbox, protocol transition or activation occurs. Semantically read-only;
do NOT set PostgreSQL READ ONLY because FOR UPDATE is required.

Valid floor0 and floor1 reads do not require X-OCWP-Write-Protocol. Preserve
quarantined/incompatible/stale-incarnation refusal and current 401/403 semantics.
A read serialized before revocation can succeed. A read waiting behind committed
revocation must see fresh authority and refuse; already delivered bytes cannot be
retracted. All legacy wildcard behavior remains frozen17, and write-only denies.

PostgreSQL18 transaction-local settings are lock_timeout=2s,
statement_timeout=5s and transaction_timeout=8s (total), set at the beginning of
the read transaction. Browser deadline is10s. Only this helper changes settings;
commands and global engine/server settings are untouched. PostgreSQL transaction
termination may invalidate a pooled connection: roll back safely and discard it
when the driver says invalid, never return an aborted/locked connection to reuse.
Budget exhaustion maps to generic no-store503 `inventory_read_unavailable`.
Any additional monotonic deadline checks supplement, not replace, database limits.
SQLite functional tests are not timeout/concurrency proof. Unsupported PostgreSQL
versions/configuration fail closed rather than silently omitting a budget.

Required actual PostgreSQL evidence: waited revoke/deactivate/scope/incarnation/
expiry; read-first ordering; competing reads/writes; 2s lock timeout,5s slow
statement,8s total across individually short statements; immediate subsequent
writer/revocation and no residual lock/mutation/admission. Representative large
product/ledger and high-offset EXPLAIN(ANALYZE,BUFFERS) must fit budgets. If not,
stop for separately reviewed index design, never raise limits or claim limit+1
bounds scan/sort cost. Hosted PG proof remains required when local PG is absent.

## Private HTTP and narrow log hygiene (R2)

Private no-store classification covers exactly `/api/v1/inventory` and children,
including trailing slash, validation/auth/internal/timeout responses. It must not
catch `/api/v1/inventory-other`. New route query validation stays bounded and
never reflects cursor payloads. Supported local edge must not retain queries.

Install an idempotent narrowly scoped Uvicorn access-log filter at existing app
logging setup, before formatter emission. For inventory namespace records remove
the complete query string while retaining method,path/status and ordinary errors;
preserve unrelated path logging. Never mutate request.scope query bytes, route
behavior, global logger configuration or all access logging. Do not log bearer,
encoded/decoded cursor, note, raw driver errors or private bodies. Correlation and
Server-Timing stay available; inventory correlation IDs are server-generated to
avoid user-controlled content entering the safe log boundary.

Test actual Uvicorn output and application error capture with synthetic canaries
for200,401/403,422 malformed/unknown/duplicate/oversized cursor/query,500 and503;
an unrelated similarly prefixed path retains its query. Inspect supported Compose
edge configuration/logs. Production SW must not cache inventory JSON or supply HTML
for inventory API navigation; existing PWA API exclusion stays intact.

## Generic connected-read capture owned by the runtime (R1)

`WorkshopController` remains sole account/session/operational owner. Add its
readonly `connectedReads` facade, declared in `runtime/connected-read.ts`, with
no inventory-specific login, persistence, offline admission or branding authority.
Public interface frozen for parallel work:

```ts
interface ConnectedReadSnapshot {
  phase: 'unverified' | 'verifying' | 'ready' | 'unavailable'
  context: VerifiedAccessContext | null
  generation: number
  message: string | null
}
interface ConnectedReadCapture extends AccountCapture {
  readonly context: VerifiedAccessContext
  readonly generation: number
}
interface ConnectedReadAccess {
  getSnapshot(): ConnectedReadSnapshot
  subscribe(listener: () => void): () => void
  verify(locationId?: string): Promise<void>
  capture(): ConnectedReadCapture
  check(): Promise<void>
  refuse(capture: ConnectedReadCapture, status: 401 | 403): void
  clear(): void
}
```

Snapshot carries no token/cursor/data. capture is request-local and immutable.
`verify` uses current bound-account location or currently selected operational
workshop; an organization-wide account may explicitly choose from runtime's current
bounded locations directory only with locations.read. Account-only directory
selection calls this metadata path, not selectWorkshop/baseline. No arbitrary ID
entry or inference from a catalog response. Without eligible scope, explain the
workshop selection requirement; inventory-only bound accounts need no directory.
No capture is available until a current, finite GET `/auth/context` succeeds.

The generic facade reads existing context metadata on floor0/floor1, permitting
snapshot_protocol null or baseline-v1 without requiring sync.pull. Use the existing
strict context conversion with a fresh immutable account/workshop generation;
metadata-only identity fields do not invent a ContextTicket or lease owner.
Never call kernel.beginVerification, baseline start/activate, or mutate a durable
context for account-only users. Expiry is the server `offline_until`, conservatively
truncated to milliseconds; here it is display/request expiration only, NEVER offline
inventory permission. Server verified_at/epoch/incarnation are captured, not inferred
from JWT or adopted from local time. Existing operational users additionally pass
the actual kernel ticket/owner/currentness fences before publishing/capturing.

Both context and inventory requests bind fetch's receiver, use cache:no-store,
redirect:error, credentials:omit, referrerPolicy:no-referrer, abort and a finite10s
deadline; expiry can shorten it. Handle current401/403 before MIME/no-store/body
validation, even missing headers/non-JSON/stalled body.401 follows existing invalid
session/logout;403 clears/holds and requires fresh verification. An obsolete capture
has no effect on a newer account. No automatic authority expansion.

Invalidate and synchronously clear context and subscribers' protected UI on account
change/logout, workshop generation, token/session generation, operational epoch/
incarnation/owner invalidation, explicit offline transition, route disposal, expiry,
nonfinite clock or rollback. Arm account-only timer even with no operational session.
On focus/pageshow/visibility, `check` runs before refreshing/read display; timers
suspended in background cannot extend expiry. Never renew expiry from an old response.
Known authority changes invalidate. New context may be obtained only through an
explicit verify/refresh; a successful inventory response cannot extend it.

## Inventory client and presentation (R3 plus review additions)

`features/inventory/{contracts,transport,controller,InventoryPanel}` consumes only
runtime.connectedReads and current runtime account/directory APIs. Transport returns
closed Product/Stock/MovementPage objects and safe error codes:
stale_request,invalid_session,capability_denied,network_error,invalid_response,
unsupported_quantity,unavailable. A stock integer outside JS safe range produces
unsupported_quantity, never rounded data or zero. All numeric wire lexemes in these
bounded responses must be canonical JSON integer literals within the safe range
before JSON.parse coercion: reject fractions/exponents including
9007199254740991.1,1.0000000000000001,1e-999. Scan lexical JSON respecting escaped
strings, then strict shape validation; retain original JSON endpoint shapes.
Safe integers ±(2^53−1) pass, ±2^53, booleans, strings/floats fail as appropriate.
Product versions and movement quantities are likewise checked before display.

Body actual bytes<=1MiB, bounded streaming/cancellation, MIME/no-store enforcement,
closed fields/IDs/scope/kind/timestamp/cursor validation, duplicate row rejection and
strict microsecond/code-point ordering. A non-null next_cursor matches the exact
last row and a full page; every continuation tuple is older than its incoming cursor.
No catalog order comparison across potentially locale-sensitive collations.

Controller owns mount generation, scope/account facade generation, product selection
generation and separate catalog/stock/history request generations/abort handles.
New work fences both late success AND late errors, including account/workshop/product
A→B→A and fetch ignoring abort. Selecting a product must not make stock/history
cancel one another. Keep one catalog page and one history page in volatile memory.
Explicit refresh only, no automatic inventory retries or prefetch/stock-per-row.

Render SKU/name/unit as plain text. Show Available quantity and last successful
received-read time, not an invented server snapshot time. Stock/history freshness,
loading/errors are separate and explicitly independent. Failed refresh clears the
corresponding value rather than leaving an unqualified balance. Older replaces the
page; Newest/refresh resets history. Display signed deltas, movement ID and localized
time; explain RESERVE negative, RELEASE/CONSUME positive hold finalization and
ADJUST signed correction. Consumption can have a negative physical-issue ADJUST
on another page; legacy history may be unlinked. Never reconstruct/group automatically.

States: loading, empty catalog, empty history, populated, denied, invalid session,
network/server error, unsupported quantity, disconnected and scope-required. Offline
clears connected data while all existing local forms/journals/delivery remain intact.
Browser online and operational sync state are hints, not proof of API reachability.
Use existing in-page section navigation and all four theme tokens; do not unmount
operational forms for inventory navigation. If any action does unmount them, invoke
the existing dirty guard and prove reject/accept and saved-journal preservation.
44px general/56px Workshop primary targets, focus after paging, announced results/
errors, full words, signs not color alone, no horizontal overflow and long text reflow.

## Proof and finite handoff

Write meaningful failing tests first, record RED then GREEN. Additional required
cases beyond INV-R01–R10: account-only idle/suspended timer expiry and late refusal;
organization-wide locations.read without sync.pull; microsecond-reversed-ID fixtures,
zero microseconds, arbitrary Unicode IDs, limit1 split consume pair, standalone
legacy CONSUME, repeated/lookahead cursor refusal and inserts on both boundary sides;
partial-grant privacy even with broader grants; raw fractional integer-rounding cases;
actual Uvicorn canaries, database-budget cleanup and unchanged business tables.

Freeze only after independent review of this ADR. Then parallel backend and client
source work with isolated file ownership. Independent exact-source reviews must
close authority, timeout/logging, numeric and lifecycle findings before handoff.
Coordinator owns publication, hosted CI/real PostgreSQL/browser/runtime/security,
ARM64 and integration with the independently owned administration-clock correction.
Do not claim its passing retry or inherited branding gates qualify current main.
Document actual executed/skipped counts, exact source/tree/manifests/logs and original
screenshot hashes. Native ARM plus three builds remains required; QEMU stays separate
nonqualifying diagnostic, physical Raspberry/Windows/Android/manual a11y open.
Stop at qualified draft read-slice integration; no next domain module in this task.
