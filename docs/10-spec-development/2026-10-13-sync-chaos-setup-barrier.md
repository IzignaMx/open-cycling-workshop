# Sync chaos baseline readiness

## Incident and scope

The qualification repeat in CI run `38426124042`, job `115395858982`,
reported four queued mutations where the large reconnect-batch journey requires
exactly three. The same journey passed on retry. This was observed on quote
PR #23, head `b847e2f3304b558e47c78c01ef926ee30cd219b9`; the sync test is unchanged
from main `b1df504bfd7d7050ee915df0bd43c55d19811a3f`.

The test checks the previous `Sincronizado` label immediately after submitting a
customer. IndexedDB can commit the customer and its queued create before the
asynchronous completion continuation updates that label. Reading the customer
ID therefore does not prove that its create was acknowledged. Disconnecting in
that window leaves the baseline create alongside the intended three mutations.

This bounded increment concerns test setup, not a production protocol change.
It preserves the exact three-operation batch and valid-operation/conflict
assertions. No release bump, schema change, dependency or ADR is needed.
Traceability: Master Agent Loop v0.2 §§7, 11, 19; QA §16 chaos injection and
§20 E2E testing; TC-SYNC-005 conflict visibility and TC-SYNC-010 convergence.
Physical-device and server-restart qualification remain separate open gates.

## Test-first investigation

A deterministic browser regression holds notification of the real IndexedDB
create transaction's completion. Durable writes are not mocked: the customer
and one pending create must exist, while the UI still shows the previous sync
state. A readiness probe must reject that state. After releasing completion,
the regression withholds the real server response and must reject readiness
again until the create acknowledgement drains the queue.

The initial diagnostic commit intentionally retains the old readiness helper
so hosted CI can establish red evidence. Local Chromium navigation remains
blocked by managed policy; no bypass is attempted. PostgreSQL is unavailable
locally, so runtime proof must come from hosted CI. Test discovery and static
checks alone are not runtime verification.

## Changelog and status

- Added deterministic regression for stale sync text and withheld baseline ACK.
- Extracted the existing readiness check without fixing it, for hosted red proof.
- Status: investigation in progress; hosted red/green evidence pending.
