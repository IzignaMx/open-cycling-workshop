# ADR · Bounded authoritative server baselines

Status: accepted for the additive, unactivated server implementation; exact-head
PostgreSQL/hosted qualification pending. Date: 2026-10-14.

## Decision

Use a full current-row scoped keyset scan, captured W/H ordered full-projection
catch-up and one durable PostgreSQL continuation family. Historical REST-only
rows are included without rewriting old feeds. All operations retain literal
account/token authority and organization → actor → family lock order. Opaque
HMAC reference tokens reuse the existing injected authentication secret with a
separate non-JWT domain; they never confer access without current bearer auth.

Two simultaneous baseline slots per user/location across epochs support two
independent devices. Absolute deadlines, 8 families per global user, 128 per
organization, one replay response per family, and indexed per-authorized-type
queries bound persistence and query candidates. SQL preflight prevents oversized
Text/JSON from crossing the application boundary before the response budget is
checked. Completed checkpoint successors preserve the original family expiry.

The [implementation contract](../10-spec-development/2026-10-14-bounded-authoritative-baselines.md)
specifies DTOs, crash-safe start/resume obligations, proof, quotas, exact replay,
activation-validation semantics and adversarial qualification. It controls this
increment, including its distinct bounded materialization and exact wire budgets.

## Migration and rollout

Add migration `0009` after existing `0008`, preserving existing business, receipt,
audit and outbox history. Future unimplemented quote persistence moves to `0010`
with down_revision `0009`; no empty reservation or prior-history change.
Downgrade permits only empty pagination metadata, under a PostgreSQL table lock held through its transaction; retained proofs cause refusal. An authorized
operator must qualify backup/restore and a schema-compatible rollback before
any installation upgrade; this source increment performs none.

Context continues to advertise `snapshot_protocol: null` pending complete server
qualification. Client production remains v4 and the identity kernel inactive.
This neither implements nor relaxes old-writer cutover, journal preservation,
restore invalidation, physical-device, accessibility or legacy-recovery gates.
Server issuance is not proof that a browser committed pages or a pending
mutation applied. Deletion, scope transfer, feed pruning and restore during a
run remain outside the create/update-only completeness proof.

Traceability: Foundation ADR-003/007/013 and TA-02/05/07;
FR-IAM-002/004/006/008; OFF-001/003/005–009/012; SEC-002/003;
NFR-004/005/010/014; INV-LOCAL-001/GATE-LOCAL-001. Preserve AGPL-3.0-only,
DCO, Offline First, Local First and explicit residual offline revocation limits.
