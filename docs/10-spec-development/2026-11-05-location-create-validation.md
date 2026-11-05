# Autonomous tests: create-location validation

## Scope and accepted baseline

The request continues useful autonomous testing while deferring physical T1–T8.
It does not accept those gates or authorize capacity, M2, deployment, quote ingress
or a release. V0.1 remains partial and R01-T035 remains open.

[PR91](https://github.com/IzignaMx/open-cycling-workshop/pull/91) merged as
`79994caf716b0ad5e41b2401075be5a1ca3f618f`, tree
`1de52d45b0d17f6332fb74216b9a71ec1f143629`.
[Fresh main CI 41995029739](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41995029739)
passed aggregate 27/27, Python 6,378 plus 58 exact skips, frontend 1,299, API one,
browser 133 direct and 133 aggregate, repeats 20/9/5/10, expiry ten and kernel 14
single-attempt passes. Runtime, Security and microfixture also passed that source.
Bounded receipts and small artifact digests were independently checked; large
browser archives, traces and screenshots were not inspected. This supersedes the
PR91 source-stage pending snapshot, but cannot qualify this changed source.

This correction follows Master Loop section 11, OFF-005/OFF-008 and canonical
R01-T018. It validates existing organization/location references, without adding
feature breadth or an architecture decision.

## Reproduction and minimal correction

56 additional real-auth HTTP probes against accepted main produced 44 passes and
12 reproducible failures. SQLite foreign keys were enabled. For organization-wide
actors, REST creates of customers, bicycles and orders with missing or foreign
locations reached composite foreign-key rejection and returned retryable 503.
The six matching admitted protocol-0 sync batches, each containing a valid create,
an invalid-location create and another valid create, also returned 503 and did
not process the trailing valid item. No cross-organization entity was written.
Protocol 1 already rejects invalid selected locations through authorization context.

The new shared check reads location ID and organization together, after writer
admission and capability/scope authorization, before create effects. REST returns
the same fixed 404 for absent and foreign locations. Sync raises a fixed per-item
`sync_conflict` inside its existing savepoint, after receipt replay and canonical
proof checks. Unexpected database failures still propagate to sanitized 503.
Foreign-key constraints remain the final integrity boundary.

Same-tenant different parent locations and a different order responsible from the
bicycle owner remain allowed, consistent with BR-002. There is no new ownership,
role, session, schema, migration, dependency, response-schema or workflow policy.
The existing conflict response classifies the failed item as permanent; this pass
does not claim new browser/Conflict Center evidence.

## Tests and verification

Durable regression RED: 12 failures and 23 passing controls. With the shared
validation, all 35 passed. Six further unexpected-database-failure controls were
added. The SQLite fixture explicitly begins transactions, so savepoints do not
accidentally commit under the driver's legacy transaction mode. It checks full
business/history snapshots, no invalid receipt, valid items on both sides and
exact replay without duplicate effects. PostgreSQL-specific cases use the existing
safe owned-schema fixture; absent local service is an explicit skip, not evidence.

Final retained regressions: 41 passed, six explicit PostgreSQL skips. Both new
files are covered by hosted shard a; the six PostgreSQL cases must execute there,
not join the accepted skip ledger. Independent review passed 382 relevant tests
and five additional probes, including protocol-1 invalid-location denial, replay
without a new location read, and mid-batch database failure remaining sanitized
503 with whole-request rollback under explicit SQLite transactions. No blocker.
The broader implementation-stage run passed 1,425 with 163 environment skips;
final-path regression collection was separately verified after relocation.

Fresh full local Python: 5,807 passed, 677 environment skips, 12 warnings in
412.03 seconds, exit zero. This includes six new unexecuted PostgreSQL cases.
Frontend 1,299 and API-client one passed with no failures/skips. Ruff, ESLint,
Prettier, mypy (125 source files), TypeScript/offline checks, OpenAPI/generated
client contracts, repository contract and PWA build passed. The existing chunk
size warning remains. Versions are Python 3.13.5, Node 24.22.1 and pnpm 11.25.0.
No dependency/lockfile changes. The full suite ran after source/test freeze;
only this documentation receipt was finalized afterward. Repository 192 and the
41-case SQLite/six-skip PostgreSQL matrix are rerun after that final receipt.

New public publication and exact-source hosted qualification remain pending;
prior PR91 approval/evidence are not inherited for this correction. No new push,
PR, CI dispatch or merge has been attempted. Remote main was rechecked unchanged
at the accepted SHA before preserving this local candidate.

## Separate backup-parser observation

38 bounded synthetic backup probes produced 23 passing controls and 15 failures
of exploratory rejection expectations. The nested PostgreSQL JSON parser accepts
identical/conflicting duplicate keys and unknown fields at five object levels;
the outer branding parser is stricter. A conflicting duplicate format version
reached a spy at restore engine creation, which stopped before any connection.
Rebinding the outer checksum is expected integrity behavior, not authenticity
bypass. No real archive, PostgreSQL command, database or destructive restore ran.

The branding documentation broadly promises duplicate/unknown manifest rejection,
but also preserves the original PostgreSQL format. It does not unambiguously
specify nested unknown-field compatibility. This is a separate parser consistency
and potential hardening observation, not proven restore exploitation or fifteen
established product defects. Rejecting ambiguous duplicate keys is a possible
bounded next step; unknown-field policy requires separate clarification. No backup
production code is changed here. Corruption, symlink/FIFO, permission, confirmation,
overlap and earlier-generation preservation controls passed.

## Evidence limits

Local exploratory probes and logs are retained in ignored
`artifacts/autonomous-locations-20261105/`; these paths are not public downloads.
The original SQLite probe used legacy savepoints and cannot establish PostgreSQL
rollback behavior. The durable regression fixture corrects that test limitation;
PostgreSQL acceptance still requires actual execution.

Native Chromium was already blocked by socket permissions in the prior pass and
is not retried or bypassed. No physical device, disk durability, power loss,
capacity, M2 or deployment acceptance follows. T1–T8/R01-T035, SPENT40927223929,
UNKNOWN41011497919 and Pages remain unchanged.
