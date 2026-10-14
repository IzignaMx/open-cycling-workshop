# Complete-command receipt proof v1

Status: accepted implementation detail of the [server cutover ADR](../02-technical-architecture/2026-10-14-server-cutover-contract.md), 2026-10-14. No installation, credential operation, server deployment, or client activation is asserted.

## Raw admission and limits

POST `/api/v1/sync/mutations` buffers at most 1,048,576 streamed bytes, regardless of Content-Length, transfer encoding, or admitted write protocol. It stops consuming immediately upon the first over-limit chunk and returns HTTP 413 `request_too_large`, before JSON parsing, authentication/database locks or item effects. The original body is replayed unchanged to FastAPI after this check.

For exact protocol 1, the outer JSON object contains exactly `mutations`, an array of 1–100 commands. Decode strict UTF-8, rejecting BOM/invalid encoding. Reject duplicate keys at every depth, non-JSON constants, unknown outer/envelope fields and missing envelope fields. The maximum JSON value depth is 64, counting the command object as depth zero; its payload is depth one. Strings contain Unicode scalar values only, with no lone surrogates. Escaped surrogate pairs representing a scalar are valid. Invalid strict input returns whole-request HTTP 422 `invalid_canonical_command` before any independent item is applied.

Every command contains all nine fields: `mutation_id`, `entity_type`, `entity_id`, `operation`, `organization_id`, `location_id`, `base_version`, `occurred_at`, `payload`. Identity strings retain their exact spelling, with no trimming, case folding or Unicode normalization; they are nonempty, at most 36 characters, and contain no Unicode whitespace. Mutation and entity IDs have exactly 36 characters, preserving the existing transport constraint. Entity type is `customer`, `bicycle` or `service_order`; operation is `create` or `update`. Payload is a complete JSON object, including keys the business create handler otherwise ignores. Base version is explicit null or a JSON integer from 0 through 9,007,199,254,740,991; booleans, strings and decimal/exponent spellings are not integer base versions. Domain validity remains a separate per-item check.

Protocol 0 retains its existing Pydantic behavior below the new byte cap. The middleware nevertheless attempts the same exact raw proof and stores positional digest-or-null results. A document-level ambiguity yields no proofs; an invalid item among otherwise valid items yields null in that position. The router treats missing positions as null. These invalid proofs do not prevent unbound legacy behavior, but a bound receipt can never use them as evidence of equality. In particular, ignored top-level fields, duplicate keys, numeric/string coercion and timestamp truncation cannot collapse changed wire inputs into a matching stored proof.

## Numeric values

Payload JSON integers are accepted only in the inclusive range −9,007,199,254,740,991 through +9,007,199,254,740,991. Decimal/exponent literals are first parsed exactly as decimal values, before ordinary JSON/Pydantic float conversion. A value is supported only when:

1. The decimal and its binary64 conversion are finite.
2. The exact decimal value equals the decimal value of Python 3.13's shortest round-trip binary64 string (`Decimal(str(float(value)))`).
3. Any numerically integral value remains in the safe-integer range, irrespective of spelling.

Thus `0.1`, `1.2500`, `1e0`, `5e-324` and `1.2345678901234567` are supported; `0.10000000000000001`, `1.0000000000000001`, `1e-999`, `1e999`, `1e20` and unsafe integers are refused. This defines a finite interoperable subset, not arbitrary decimal precision or exact binary representability. No value is rounded into admission. NaN and Infinity are refused even though some parsers accept them.

Numbers serialize in ordinary decimal notation, without exponent, unnecessary fractional trailing zeroes or trailing decimal point. Negative zero serializes as `0`. Numerically equivalent supported JSON number spellings serialize alike; strings and booleans remain distinct. No ambient Decimal context normalization is used, because it could round retained digits.

## Timestamp values

An aware string has exactly `YYYY-MM-DDTHH:MM:SS`, optional 1–6 fractional digits, and `Z` or signed `HH:MM` offset. Only ASCII decimal digits and uppercase `T`/`Z` are accepted. Offset hours are 0–23 and minutes 0–59. Unknown offset `-00:00`, naive/numeric/boolean timestamps, leap seconds, invalid dates and more than six fractional digits are rejected, including a seventh trailing zero. UTC conversion must remain representable in Python's years 0001–9999.

Normalize to `YYYY-MM-DDTHH:MM:SS.ffffffZ` with exactly six fractional digits. Equivalent known offsets produce equal timestamps. Each microsecond is retained; no truncation or rounding establishes equality.

## Canonical bytes and hash

Canonicalize the complete command with the normalized timestamp:

- Objects sort keys lexicographically by Unicode scalar/code-point order, including nested payload objects. This is Python string ordering, not UTF-16 code-unit ordering.
- Arrays preserve element order.
- Strings use JSON double quotes and mandatory escaping of quotation marks, backslashes and controls; UTF-8 scalars otherwise remain unescaped. Python `json.dumps(..., ensure_ascii=False)` supplies the fixed escapes (`\b`, `\t`, `\n`, `\f`, `\r`, otherwise lowercase `\u00xx`). Slashes are unescaped. No normalization changes combining sequences.
- Null/booleans use `null`/`true`/`false`; numbers use the rules above. There is no insignificant whitespace or final newline.
- Prefix the JSON bytes with the exact ASCII bytes `ocwp-sync-command-proof-v1\n`, where `\n` is one LF byte. SHA-256 of prefix plus UTF-8 JSON produces the lowercase 64-hex digest. Persist proof_version = 1.

The authenticated actor is persisted separately from this digest. The client neither computes this proof nor claims its actor. SHA-256 provides equality support, not authentication or an authorization grant.

## Fixed vectors

All IDs and names below are synthetic. The first input has timestamp `2026-10-14T12:30:00.123456+02:30`, negative zero in its payload, and nested combining/noncombining Unicode keys. Its canonical JSON after the prefix is:

```text
{"base_version":null,"entity_id":"01929840-0000-7000-8000-000000000002","entity_type":"customer","location_id":"loc-1","mutation_id":"01929840-0000-7000-8000-000000000001","occurred_at":"2026-10-14T10:00:00.123456Z","operation":"create","organization_id":"org-1","payload":{"display_name":"Ána 🚲","ignored":[null,true,false,0,1.25,{"é":"é","é":"é"}]}}
```

SHA-256: `2df7459256df801b5f752e17a6efb632daf13fd1bdd6cf7612b77a67cd432c42`.

The second vector fixes controls, array ordering, explicit base version and zero fractional timestamp:

```text
{"base_version":0,"entity_id":"01929840-0000-7000-8000-000000000002","entity_type":"customer","location_id":"loc-1","mutation_id":"01929840-0000-7000-8000-000000000001","occurred_at":"2026-10-14T10:00:00.000000Z","operation":"update","organization_id":"org-1","payload":{"a":[1,2,3],"z":"\n\t\u0000"}}
```

SHA-256: `bda4c6ebe1a5969752a5e0257a4a517900a4113bb77f0b86fc240add670b2d3e`.

The literals and independent fixed SHA-256 expectations live in `services/platform/tests/sync/test_command_canonicalization.py`. They test canonicalization separately from whether a domain update is meaningful.

## Stored proof and effect boundaries

Nullable `actor_id`, `command_digest` and `proof_version` are all null for existing/legacy receipts. Database constraints enforce all-or-none fields, version 1 and lowercase 64-hex digest. The service independently validates metadata so partial/corrupt/unknown proof versions cannot fall back to legacy behavior even in corrupted/imported storage.

After ordinary current authorization and request-level admission:

- All-null receipt, protocol 0: retain the old organization/location/entity/type/operation replay match. No payload/actor proof is claimed.
- All-null receipt, protocol 1: `legacy_receipt_unverified`.
- Valid bound receipt, either protocol: require authenticated actor and exact raw command proof. Differences yield `receipt_proof_conflict` without disclosing which proof component failed.
- Invalid stored metadata, unavailable exact incoming proof, or an internal raw-proof/envelope mismatch: `receipt_integrity_conflict`.
- Cross-organization global mutation-ID collision: generic `sync_conflict`, without actor/proof disclosure.

Original result/version is replayed without new domain, event, receipt, feed or outbox effects. Receipt proof/version/old columns are never rewritten. Payload actor claims do not become receipt actors. New protocol-1 effects require the raw proof, and the service independently verifies it against the envelope to catch misaligned integration. Protocol-0 new receipts remain unbound.

`SyncApplicationContext` carries authenticated actor, write protocol, exact raw digest and owning session identity. A session ID or merely active transaction is insufficient admission. After the real organization/actor/floor/incarnation/expiry barrier, `lock_writer` records the exact root transaction object, effective principal and write admission on the session. Ordinary `SyncService.apply` requires that issued record and the same still-active root transaction, binds actor/protocol/organization to it, and rechecks expiry, sync capability, entity capability and location scope. Commit or rollback makes the retained record unusable in a later transaction; nested per-item savepoints remain valid. `SyncService.for_fixtures` is an explicit fixture/seed-only path, absent from HTTP and CLI. It does not waive protocol-1 proof validation. Request admission owns locks/expiry/floor/epoch outside item savepoints. Typed item conflicts preserve independent saves; request refusal remains whole-response. These guarantees assume every server/writer implements the cutover contract, never a mixed pre-cutover binary pool.

## Evidence and limits

Observed preimplementation red: bound protocol-0 actor replay and protocol-1 legacy replay each incorrectly succeeded (`DID NOT RAISE SyncConflict`). Independent review also reproduced a bare active-transaction admission bypass (`DID NOT RAISE RuntimeError`); the barrier-issued transaction record and direct-service authority checks close it. Focused parser, receipt and actual ASGI tests cover both fixed vectors, equality/changes, canonical rejection, streamed limits, metadata constraints/corruption, raw protocol-0 downgrade attempts, exact historical preservation, owned admission and independent savepoints. Final integrated counts and PostgreSQL contention evidence belong to the increment qualification report. SQLite/function tests do not establish PostgreSQL concurrency, rollout safety, real recovery or browser preservation.
