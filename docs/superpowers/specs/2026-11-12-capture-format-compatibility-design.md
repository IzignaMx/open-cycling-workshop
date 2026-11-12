# Preventive capture reader compatibility baseline

## Decision and scope

The user requested compatibility work before selecting an existing bicycle.
Baseline is PR103 main cc18a203a8c754284fc14ef3570d94d7d98fac23. This increment
changes only the preventive reader/maintenance boundary. All production writes
remain exact format 1. No existing-bicycle field, selector, new store or database
version is enabled. It is an integrity/recovery prerequisite under Master Loop
§5/§16, OFF-007 and the approved capture recovery design, not full V0.2 admission.

An unchanged historical v8 reader rejects unfamiliar payloads and deletes their
rows during startup maintenance. Dexie 4.4.4 retries VersionError without a version:
a v8 client can reopen a v9 database. Neither versionchange nor a version bump
excludes that reader. A compatible partial draft plus sidecar risks reduced old
submission and old logout misses private sidecar bytes. These shortcuts are rejected.

## Exact preservation contract

The lifecycle envelope remains fixed: exact current top-level fields `format`,
`checkpointId`, `generation`, `channel`, `revision`, `firstPersistedAt`, `expiresAt`,
`draft`, and `retainedSelection` only for order. The channel is customer/order;
IDs are canonical UUIDs; revisions/timestamps are nonnegative safe integers;
expiry is exactly firstPersistedAt + 86,400,000 with no overflow. Payload format
is a positive safe integer. A known v1 checkpoint must match channel, generation,
revision and both timestamps. No unknown checkpoint schema is inferred.

- Supported: exact existing format 1 validator, unchanged.
- Unsupported but preservable: format >1, valid fixed envelope, plain JSON payload
  within the existing 65,536-byte projection bound. Payload meaning is opaque.
- Corrupt/unclassified: invalid metadata, unknown envelope fields, invalid JSON,
  over-limit payload, or invalid current format 1. Existing refusal/corruption
  behavior is unchanged; unsupported does not widen the current v1 parser.

The current reader preserves unexpired unsupported bytes while the existing
checkpoint is open, UNSENT, matching and within its validated clock bounds. It
never hydrates them, down-converts, overwrites or protects/submits them. A clock
rollback preserves unsupported bytes and reports unresolved maintenance instead
of inferring expiry; current-format corruption policy is unchanged. Load/save/
protect refuse with a distinct unsupported-format reason and an explicit message
that compatible software is required. No automatic relogin or migration is offered
as recovery. Other admission, CAS, writer epoch and unknown-result fences remain.

Expiry uses only the fixed verified lifecycle metadata and matching checkpoint,
not fields inside the opaque payload. Authorized explicit logout/discard and scope
retirement retain the existing exact-generation cleanup semantics in the same
canonical store. Cleanup aborts cannot acknowledge deletion. Missing/mismatched
metadata never becomes a restoration or submission permission. No new retention
period, private duplicate or payload in logs is introduced.

## Compatibility and rollback gate

Before activation of any future payload, reverting this release to historical v8
is safe only because this release still emits v1. This does NOT make historical
binaries forward-compatible. After future activation, the minimum rollback target
must be this compatibility-aware baseline or newer, preserving unknown payloads
while refusing operation. Exclusion of pre-baseline offline readers is a separate
unresolved release gate. Service-worker update, elapsed time or a feature flag
alone is not evidence of exclusion. The selector remains blocked.

## Proof strategy

Pin actual old validator/store bytes and their hashes to the baseline commit;
transpile them independently rather than mocking the legacy parser with new code.
Against one isolated fake-IDB factory prove the historical deletion counterexample,
actual old load refusal and Dexie v8-to-v9-to-v8 reopen. Test current-reader exact
byte/TTL/CAS preservation, explicit refusal, old valid v1 roundtrip, expiration,
authorized cleanup, malformed envelope controls, and transaction-abort safety.
Actual runtime reload must show an explicit blocked recovery message and no new
journal/network side effects. Native browser/physical/rollout exclusion evidence
remains separate and must not be inferred from fake IndexedDB.

## Explicit departure protection

An unsupported refusal includes only the validated checkpoint metadata, never
content. The runtime keeps admission inactive and treats the retained opaque
draft as unsent for the existing leave confirmation. Cancel leaves its bytes
unchanged. Confirmed logout or workshop discard uses the existing exact-generation
cleanup; a stale generation cannot remove replacement data. No payload is
hydrated, interpreted, or rearmed by retaining this cleanup identity.
