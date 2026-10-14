# ADR · Server cutover contract (Increment B)

Status: accepted implementation contract, 2026-10-14. Runtime qualification is
recorded separately; acceptance does not assert deployment or client activation.
Base: actual main35 `68933a7c61c9ed13a5f5634f3f9c3df69154f22d`, product tree
`957fb12edf0c3f0afcb93e89fc748ce68a4544c2`.

## Sources and bounded supersession

This implements the independently reviewed finite A/B/C cutover plan and its
accepted four amendments: restore-resistant signed session incarnation, explicit
dataset provenance, stored-proof replay independent of incoming protocol, and
unconditional safe downgrade refusal. It supersedes only the temporary null-only
advertisement/policy decisions in the authenticated-context, bounded-baseline and
isolated-context-adapter ADRs. Their historical evidence remains historical.
Foundation ADR-003/007/013 and TA-02/05/06/07, FR-IAM-002/004/006/008,
OFF-003/005/007/009/012 and SEC-002/003 govern this contract. AGPL-3.0-only,
DCO, literal operational grants and append-only history remain unchanged.

Increment B changes server contracts and isolated strict context parsing only.
Production App/repositories remain v4, without kernel activation or UI work.
Increment C owns immutable journal incarnation, overlay/replay holds, ongoing
deltas, same-session offline reload, production integration and old-bundle/SW
native-browser journeys. No real credentials, installation, activation, restore,
persistent access or deployment is performed by this development task.

## Durable compatibility and exact ingress

Migration `0010` follows `0009`; the unimplemented quote reservation moves to
`0011` (down_revision `0010`). Every organization gains
`minimum_write_protocol` (exact integer 0 or 1, default 0) and
`dataset_incarnation` (canonical lowercase UUID). Missing/partial/corrupt state
fails closed, never initialized by ordinary HTTP. Bootstrap initializes metadata
atomically at floor 0 and refuses any existing organization/location/user state.
The migration is forward-only: downgrade always refuses before any DDL/DML,
even for an empty database. Only a schema-compatible binary enforcing this ADR
is a supported application rollback. Never erase proof or lower a floor.

The exact header is `X-OCWP-Write-Protocol`. Absence or exact `0` is legacy;
exact `1` is the implemented strict caller contract. Unknown, whitespace-altered,
comma-joined and duplicate headers are refused. A header is not authorization
or proof of bundle identity. Admission locks and refreshes the organization,
validates state/floor, then locks/reloads actor and preserves the incoming literal
effective authority; locks last through commit. Floor 1 rejects legacy requests
with whole-response HTTP 409 `client_upgrade_required`, before receipt or
business/audit/feed/outbox effects. No per-item success masquerades as refusal.

Covered writers: POST `/api/v1/sync/mutations`, `/customers`, `/bicycles`,
`/service-orders`, `/service-orders/{id}/transitions`, `/inventory/products`,
`/inventory/movements`; POST/PATCH `/admin/users` and user revoke-sessions /
reset-password; POST `/locations`, `/auth/logout-all`, `/auth/change-password`.
There is no emergency security-writer exception. All paths use organization →
actor → target/product ordering. Inventory service admission remains inside
`record_movement`; product creation remains admitted at its router boundary.
First-owner maintenance explicitly supplies compiled protocol 1 under the same
barrier. Fresh bootstrap is an exclusive fresh-install exception. Internal
production orchestration requires transaction-owned admission; fixture-only
service calls are explicit test contexts. Worker job metadata is excluded: no
business handlers are registered. Future business handlers must join this
barrier before domain locks. Quotes have no persisted writer and blobs no upload
route. Migration/restore/fixture maintenance requires offline, drained writers.

`OCWP_CUTOVER_ENABLED` defaults false. A qualified enabled server at floor 1
advertises and admits strict protocol 1; disabled servers refuse strict writes.
At floor 0, an enabled implementation may honor strict receipt writes but does
not advertise baseline support or allow ordinary client activation. This overlap
never permits old binaries: drain/replace every API/maintenance writer before
sending protocol-1 traffic or activating the floor. Metadata cannot fence a
binary that never checks it.

## Signed session and context contract

Login remains available and locks organization → account before verifying
current password/account state and issuing a token. New tokens carry signed
`di`, the current dataset incarnation, using the existing signer/secret. Missing
`di` is legacy and admitted only at floor 0. Present malformed or mismatched `di`
is always 401; floor 1 also rejects missing `di`. Preserve original validated
claim and expiry, and recheck after lock waits and before strict write commit.
All authenticated reads and writes enforce incarnation, including `/auth/me`,
context, baselines, admin and inventory. Recovery rotates incarnation, never
increments restored session counters into potential collision.

Closed `/api/v1/auth/context` and nested start/activation contexts require
`dataset_incarnation` and policy `ocwp-access-baseline-2`; `snapshot_protocol`
is exactly null or `baseline-v1`. Genuine enabled floor 1 yields `baseline-v1`;
floor 0 or disabled composition yields null. The epoch hashes the previous
identity/scope/literal-resolved grants/session inputs plus incarnation, durable
floor and effective support policy. Configured endpoint remains client realm;
server `api_realm` stays null and is never inferred from Host/forwarded headers.
Context/start/activation share one builder. Null must not enable ordinary client
baseline requests, READY or offline reuse. Diagnostic baseline metadata endpoints
retain the existing bearer-bound read protocol; they are no business-write bypass.

Strict sync additionally requires one exact `X-OCWP-Authorization-Epoch` header
and one selected location shared by the batch. Under the same org/actor barrier,
compute current context and compare the supplied epoch before item savepoints.
Missing/invalid/stale epoch or mixed locations is whole-response 409
`authorization_context_changed`. No silent substitution. REST/admin require
write protocol and fresh authority, not a workshop projection epoch.

## Immutable complete-command receipt proof

Receipts add nullable `actor_id`, `command_digest`, `proof_version`. Legacy
columns remain byte-identical and all three new fields remain null on old rows.
Persistence enforces all-or-none, version 1 and lowercase 64-hex digest.
Bound proof is enforced on either admitted incoming protocol: original actor
and complete canonical command must match. Legacy receipt/protocol 0 at floor 0
retains historical matching behavior; legacy receipt/protocol 1 gives typed
`legacy_receipt_unverified`. Unknown/partial/corrupt proof yields
`receipt_integrity_conflict`; changed actor/command yields
`receipt_proof_conflict`. No actor inference from events. Current authorization
precedes any receipt disclosure; cross-organization collisions are generic.
Independent command conflicts retain savepoints; request admission is atomic.

Canonical proof v1 includes a domain separator, organization/location,
mutation/entity IDs, entity type, operation, base_version, exact supported UTC
microsecond timestamp and complete payload (including ignored business keys).
UTF-8 strings retain Unicode exactly; no normalization, surrogates or nonfinite
numbers. Keys have deterministic order, array order is preserved and primitive
types remain distinct. Strict input rejects duplicate JSON keys, unknown envelope
fields, coercion, unsafe/unrepresentable numbers and naive/numeric/sub-microsecond
timestamps. Mutation bodies are byte-bounded before JSON parsing. Fixed golden
vectors and exact representability rules accompany the implementation. SHA-256
supports equality only; authenticated actor and current authorization remain
required. Protocol 0 cannot bypass proof by parser coercion of a bound command.

## Operator activation and isolated restore

Local commands are `ocwpctl cutover status|activate|recover --organization-id ID`.
They use already securely configured DB access, never a browser toggle or new
credential. Activation requires qualified enabled composition, locks state and
changes 0→1 with secret-free append-only organization audit; matching active
state is idempotent without duplicate success audit. No lowering command.
Fresh installs need this explicit activation before the future new PWA is usable.

Restore keeps API/edge/workers/all writers stopped. Upgrade/cutover a floor-0
snapshot explicitly while isolated first. Recovery requires active floor 1,
current schema and `--expected-incarnation UUID`; under lock exact-match CAS
rotates to a new UUID and appends honest organization provenance (null target_id)
atomically. Preserve credentials, grants, versions, receipts and business/journal
history. Reusing the old precondition refuses without rotation or success audit.
After uncertain output inspect state/audit; never blindly retry with a new
precondition. Only then verify old-token/checkpoint refusal and fresh login/
baseline in isolation before reopening qualified API/edge. Workers remain stopped
pending existing outbox review. Old-incarnation journals require recovery holds;
no automatic resubmission. Session_version++ is not recovery invalidation.

## Finite evidence and limits

Required: red→green admission/header/receipt/token/epoch matrices, preserved
legacy history, actual advertisement, migration preservation and unconditional
refusal; real PostgreSQL writer-first/floor-first/rollback/independent-org and
two-process blocker-graph contention; restored-counter collision, stale recovery
CAS and rollback. Existing PR35 inventory stock/finalization/contention remains.
Generated OpenAPI/types, static/aggregate checks and independent review must be
current. Hosted exact-tree proof is separate from local skipped database tests.
C supplies actual production old-bundle/SW queue preservation and integrated
browser journeys. Physical devices, actual installs and broader money/parts/
purchasing scope are not implied by a code-qualified development MVP.
