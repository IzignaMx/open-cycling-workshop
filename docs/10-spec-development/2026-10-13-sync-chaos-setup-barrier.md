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

The initial diagnostic commit retained the old readiness helper so hosted CI
could establish red evidence, now confirmed below. Local Chromium navigation remains
blocked by managed policy; no bypass is attempted. PostgreSQL is unavailable
locally, so runtime proof must come from hosted CI. Test discovery and static
checks alone are not runtime verification.

## Hosted red evidence · 2026-10-14

- Draft PR #24 diagnostic head: `35118af37378bbf2b86c3d071b715ddd67b609d8`.
- CI run `38541165450`, job `115775986709`; tested synthetic merge
  `3a9373383e3658cf44a411a0555dd40229d18048`.
- The regression failed at its first readiness probe: the promise **resolved**
  with a customer ID instead of rejecting while the baseline create remained
  pending. Both its initial attempt and retry failed identically; the other
  nine browser journeys passed. The qualification repeat reproduced the failure.
- Head and tested-merge trees both equal
  `15f5b788c4c65b1c5a1084bc11f5beb19a8df00f`.
- Qualification artifact: `11882193139`, overall failed as expected. This is
  red regression evidence, not successful release qualification.

## Corrective setup

The common readiness helper now requires local-save completion, the unique
baseline customer ID, an empty durable queue, the synchronized UI state, and
server confirmation of that same customer at version 1. The negative regression
probes require the specific local-save and queue-acknowledgement failures;
unrelated exceptions cannot satisfy them. The withheld response is a real
successful create ACK, verified as applied at version 1 before release.

The out-of-band update must return the same mutation/customer IDs with applied
status and entity version 2 before queuing the stale local update. The exact
three-mutation assertion, queue drain, visible conflict and both independent
valid creates remain required. Unique per-run names avoid reusing prior rows or
feed entries during retries/repetitions.

CI additionally repeats both affected journeys five times each with one worker
and zero retries. This is bounded repeat evidence, not a claim that all possible
browser schedules are covered. No assertion or timeout is weakened.

## Changelog and status

- Added a deterministic regression for stale sync text and withheld baseline ACK.
- Replaced label-only readiness with durable local/server setup barriers.
- Verified the remote update result before constructing the stale conflict.
- Added unique scenario names and a retry-free CI repeat gate.
- Initial independent review validated the transaction hook and suggested unique
  names and specific rejection diagnostics; both suggestions are incorporated.
- Status: implemented pending hosted green evidence; production code unchanged.
- Local corrected-tree qualification after integrating inventory main `b1d3a5d`:
  21 checks passed, zero failed, five environment blockers; Python 370 passed /
  eight PostgreSQL skips, frontend core 72 passed, API client one passed, static
  checks/contracts/typechecks/PWA build passed. Focused strict TypeScript compile
  of the E2E spec passed; both normal and repeat-gate test discovery passed.
  Discovery is not execution. Hosted corrected-tree browser proof is pending.
