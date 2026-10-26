# Full retained quote history before recovery rotation

Status: implemented pending exact-candidate hosted evidence. No installation,
reopening, quote activation or deployment is authorized by this source increment.

## Integrated baseline and preserved evidence

PR #58 merged on 2026-10-26 as `9e5bea10ec041682e63d04e3bb2d2a484a3a6196`,
with tree `09b76901555f75f702744e6165ae4fe837c9f1df`. Its reviewed predecessor
head was `9c2aebe73602bc9933676627d441cd862989a3b8`; CI `40377559080` passed
27/27 controls, 4,635 Python cases with 58 exact expected skips, all six mandatory
restores and both cleanup proofs. Direct/aggregate browsers each passed 86/86
without retries or flakes. These remain named-source results, not evidence for
this changed tree. Postmerge CI `40396434262` failed qualification: shard A's canary Docker create
hit its unchanged command timeout (`creation_uncertain`) before collection, with
an empty CID file. Both A primary and independent cleanup prove `verified_absent`;
the failing finalization step rejects qualification, not cleanup. Shard B collected
1,993 cases, passed 1,946 with 47 expected skips and verified both cleanups; the
paired receipt is failed. Terminal aggregate qualification is **24/27**: only
`python_tests`, `python_psycopg` and `postgresql_integration` reject
`receipt_failed`. Direct and aggregate browsers each passed **86/86**, with zero
failed, flaky or skipped cases. Security, Local runtime/native ARM64 and
containment passed. This current empty-CID cleanup evidence does not establish the old
failure's cause or absence. No postmerge qualification is inferred, and no
identical-head rerun or timeout widening follows.
The optional failed QEMU diagnostic remains nonqualifying. Historical
`40249194704` container absence remains unproven; no later result repairs that
history. Physical Windows/Android/laptop/Raspberry acceptance remains deferred.

## Requirement and implementation boundary

This closes the implementation gap called out in
[semantic closure](2026-10-17-quote-semantic-closure.md), subject to hosted proof,
and implements [bounded effects §§6–8](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md).
The existing `cutover recover` command now validates before generating a fresh
incarnation or appending its recovery audit, in the same owning transaction and
under the existing organization writer barrier.

- Scalar existence probes inventory retained revisions, lines, decisions,
  operations, targets and quote outboxes. Orphan/mismatched ownership, extra quote
  outboxes and shared effect identities fail closed; claims on a local lineage or
  revision are checked even when the child claims a foreign organization.
- Every scoped lineage is keyset-enumerated, one at a time. Existing bounded order
  scalar loading and complete quote reconstruction validate every retained
  revision/decision/proof/result and every versioned generic change/outbox pair.
  No summary, hash cache, current-head-only check or synthetic authority replaces
  source validation. Existing per-lineage bounds and generic byte guards remain.
- Unsupported/partial tuples and invalid stored metadata return the existing fixed
  `quote_integrity_failed` category. Database interruptions remain availability
  failures, not corruption findings. Failure leaves incarnation, audit, receipts,
  effects and original malformed evidence unchanged.
- Schemas 0010/0011 retain recovery only when quote tables and scoped quote outbox
  evidence are absent. Empty 0012
  retains recovery after orphan inventory; populated 0012 is explicitly refused
  with `quote_recovery_schema_required` until preserved forward migration to 0013. No legacy receipt is assigned a version or rewritten. Valid historical
  quote-only decisions still replay without new order transitions.
- Targets lack an organization column. A target with no retained revision/source
  or target line cannot safely be attributed; it conservatively blocks recovery
  globally rather than disappearing through an inner join. Valid unrelated
  organizations remain outside scoped reconstruction.
- Quote-only history never hydrates current order Text. Oversized unrelated legacy
  orders remain untouched. Outbox delivery bookkeeping is not republished or reset.

This is a maintenance gate, not an endpoint activation or automatic reopen. All
application/worker/old-writer processes must remain stopped on the isolated
restored target throughout validation/rotation and until separate acceptance.
The organization barrier orders supported application writers; it does not fence
privileged concurrent SQL, physically damaged metadata or hostile schema changes.
No total installation-size runtime/capacity claim follows from bounded per-lineage
allocation. Preserve browser journals, originals, TLS and verified backup.

## Evidence and remaining gates

TDD first demonstrated two real failures: corrupt retained generic outbox content
and corrupt lineage decision sequence both allowed recovery rotation (2 failed,
1 positive control passed). The candidate refuses both before rotation.
Focused SQLite tests cover full enumeration including a corrupt later lineage,
orphans/foreign claims, unsupported versions, quote-only oversized current Text,
0012 refusal/preserved upgrade, unchanged replay effects and transaction rollback.
SQLite is functional evidence only, not PostgreSQL locking/restore qualification.

Local Python 3.13.5 verification: the focused recovery/operator/reconstruction/
atomic-effect/metadata selection passed **198**, with **118 pre-existing local
PostgreSQL/dependency environment skips** (not the hosted suite's 58 intentional
skip identities). Full collection is **4,713** cases: the previous 4,693 plus
20 SQLite regressions. Strict mypy for both touched production roots, Ruff check
and format for four Python files, repository contract, OpenAPI/generated
TypeScript consistency, touched documentation formatting and diff whitespace
checks pass. No PostgreSQL run is inferred from collection or these local skips.

The existing mandatory real service-effect restore test now commits a tiny
ordinary-SQL retained outbox mismatch in its isolated restored target, requires
recovery refusal and unchanged retained rows/incarnation, and restores the exact
original bytes **only in the fixture** before its original successful recovery,
stale-session rejection and fresh-authority same-ID replay assertions. Production
validation never repairs. Six required restore identities, exact expected skip
identities, workload/resource limits, assertions and ownership controls are
unchanged. That new PostgreSQL path is pending hosted execution, not locally passed.

Independent source review closed without blocking findings after fixing foreign
quote-outbox/local-lineage and prequote-schema evidence omissions. Independent
focused recovery/operator retest passed **89** cases; Ruff and diff checks passed.
Final exact-tree normal CI and real PostgreSQL restore remain required. Installation
inventory, physical corruption qualification, real-volume RPO/RTO, physical devices,
capacity/latency, ingress/authority/adoption/old-writer gates and quote API/UI
activation remain separate. No old bounded workflow trial is relaunched.
