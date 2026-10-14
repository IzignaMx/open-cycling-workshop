# ADR: isolated bounded baseline consumer

Status: independently reviewed isolated implementation; native hosted proof pending.
Base: integrated main34 `2723ec321a606a69a2516f1eaea4d96600354f8f`, tree
`033665e81c4b547da715c8f12441a72f650ef94d`.

## Scope and authority

Add a bounded initial-baseline consumer for customer, bicycle and service_order,
without importing it from production App, auth, repositories or defaultDB.
Server authentication and literal capabilities remain authoritative. Preserve
AGPL-3.0-only, truthful DCO, Offline First/Local First, immutable journals and
actual migration history. Traceability: Foundation ADR-003/007/013, TA-02/05/07;
FR-IAM-002/004/006/008; OFF-001/003/005–009/012; SEC-002/003;
NFR-004/005/010/014; INV-LOCAL-001/GATE-LOCAL-001.

The actual server and context adapter still expose `snapshot_protocol: null`.
Ordinary coordinator start/resume/step returns BASELINE_REQUIRED without HTTP;
ordinary activation, active-cache reuse, reads, dispatch and offline eligibility
require a supported protocol and complete matching metadata. No allow-null
configuration exists on those paths. Supplying local metadata is not
cryptographic proof or a substitute for trusted server transport.

## Boundaries and persistence

- `baseline-wire.ts`: closed runtime DTOs, three projection schemas, strict
  integer/identity/scope/capability checks and microsecond-preserving UTC equality.
- `baseline-transport.ts`: immutable identity/session/bearer/body capture, exact
  destination, no redirects/cookies/referrer, no-store, bounded streaming decode,
  sanitized status-paired errors and Retry-After. A request never consults a
  mutable token provider after it begins. Bearers are never persisted.
- `baseline-state.ts`: versioned metadata and completion eligibility validation.
- `baseline-store.ts`: lower-level fenced IndexedDB staging transactions, no HTTP.
- `baseline-coordinator.ts`: ordinary supported-protocol admission and one bounded
  HTTP step per call, with explicit retry outcomes rather than hidden timers.
- `AccessKernel`: session admission and post-commit volatile ticket fencing.

CachePartition gains optional, non-indexed `baseline` metadata with `format: 1`.
Existing stores/indexes and Dexie v1–v5 migrations are unchanged. This is a record
format addition, not a new or rewritten schema migration. Quote v6 remains an
unimplemented reservation; SQL 0009/0010 history is untouched. Missing, unknown or
contradictory metadata cannot establish a completed baseline. Existing records,
preferences, unknown legacy fields and journals remain present.

Before start HTTP, one transaction creates a fresh empty private partition and
persists a canonical UUID request ID, exact start body, original/current owner
and context binding. Abandonment requires another partition and request ID;
retry preserves both. Old partitions are superseded, not deleted. Storage growth
and quota exhaustion remain explicit limitations; no automatic cleanup occurs.

Metadata retains original validated timestamp spelling, so normalization cannot
expand a valid near-limit response beyond its storage bound. It retains an
immutable original StartResponse (at most 16 KiB), separately
from one latest canonical page/finalize receipt (at most 1 MiB), next exact
request, phase, checkpoint and bounded retry/hold metadata. It does not retain
an unbounded receipt history. Continuations are opaque routing metadata, not
credentials. Never derive cursors, expiry or authority by decoding them.

## State, atomicity and replay

Phases are start_pending, scan, finalize_pending, catching_up,
activation_pending and active. Scan completion alone is not complete data.
Finalize captures the finite server catch-up interval; matching delta completion
only reaches activation_pending. An actual server validate-activation response
must match baseline, epoch and exact checkpoint before the ordinary activation
transaction can make the partition active and READY.

Every ingestion transaction compares generation/tab/partition, principal/epoch,
context, owner and exact expected request; validates the entire bounded response;
merges rows; and persists receipt plus continuation atomically. Newer versions
win, older versions cannot overwrite, and equal-version unequal canonical
projections abort the entire transaction. Equivalent timestamp offsets compare
equal without dropping microseconds. No baseline result acknowledges a command.

Crash/reload sees either the prior request or its committed successor. A lost
response retries the exact predecessor under freshly captured current transport.
Only an exact canonical original-wire latest response can be accepted as a duplicate without
effects. Older responses fail. Every late StartResponse after durable start
commit is rejected, including its exact original: it cannot rewind progress,
renew a deadline or replace newer state. A last near-budget record may precede
an empty completion page; this is handled without skipping values.

Reload requires fresh online verification before resuming incomplete staging.
Only equivalent realm/principal/location/epoch/policy/account location/concrete
grants may rebind ownership; original request/evidence and progress remain.
Changed authority requires a fresh partition. A pending last delta can replay
after the old scan deadline if the server already completed and retained its
family; local phase cannot decide that outcome. Recorded server expiry/integrity failures
cannot be resumed as if their checkpoint were valid. Initial activation and
subsequent incremental consumption are distinct: this slice does not implement
ongoing incremental runs or production offline-reload admission.

An active partition's flags alone are insufficient. Completion validation is
shared by existing acceptVerifiedContext and authorized/read/dispatch/offline
paths. It checks format, bindings, original start evidence, completed delta
receipt and exact checkpoint/cursor. Synthetic test fixtures now supply this
full evidence instead of weakening ordinary checks.

## Races and failure behavior

After durable completion, volatile ticket assignment checks a consistent current
control/partition/context snapshot, generation, tab, partition, epoch, principal,
local sequence and exact expected prior ticket. A late same-generation start or
activation cannot replace a newer partition. Concurrent local starts are refused
without invalidating the committed winner. Hold transactions compare the same
owner and expected request before updating state; stale failures cannot hold a
new partition. Transport/session guards are checked again inside page/activation
transactions.

401 locks the matching attempt for verification; 403/changed authority holds it.
410 and stale/inconsistent continuity require a fresh baseline. Network/capacity/
temporary-unavailable outcomes preserve the request and return bounded backoff
with jitter, respecting a longer safe Retry-After rather than shortening it.
Retries pause offline; exhausted retries hold visibly. Quota abort rolls back
rows and continuation. If even writing HELD fails, the coordinator reports a
storage-or-fence failure and disables the matching volatile session until fresh
verification, rather than claiming the hold was persisted. Captured-current
checks prevent stale failures from disabling a newer winner. No retry,
refresh or recovery deletes or relabels the original journal/delivery/events.

## Qualification boundary and future negotiation

Only `tools/kernel-browser` composes lower-level staging with the actual
null-advertised FastAPI server. It can exercise start/page/finalize/delta and
validate-activation and inspect durable results without pretending ordinary
supported-protocol activation succeeded. Its synthetic qualified fixtures and
inspection helpers are outside the production import graph. Null-protocol
qualification evidence remains unusable through ordinary kernel paths.

A later, separately reviewed advertisement change must update the server schema,
consistent context/start/activation composition, epoch semantics and generated
contract, then test genuine supported-protocol negotiation. No browser rewrite
of null, test-only header or fake server response establishes this proof.

Production activation still requires old-writer compatibility floor and atomic
ordering across every ingress, old service-worker/tab qualification, restore/
session invalidation, production auth/repository integration, ongoing deltas,
offline-reload admission, recovery/receipt provenance, accessible held UX and
physical-device gates. The existing production Golden Slice stays on v4.
A separate database name is cooperative isolation, not an ACL: arbitrary
same-origin code/device owners can access storage, and offline old tabs cannot
be remotely revoked. No cutover, legacy attribution, oldDB deletion, branding,
installation or deployment is included.
