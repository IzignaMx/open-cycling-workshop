# ADR · Isolated identity-bound offline kernel

Status: accepted for the bounded isolated implementation; local checks recorded,
independent/hosted qualification pending.
Date: 2026-10-14.
Base: PR #28 head `1ab3554d` (structural themes plus access administration).

## Context and scope

The existing local operational stores and sync queue are scoped by organization
and location, not by authenticated author. Two users with the same workshop and
capabilities can therefore share a working set. A React session-generation guard
can suppress a late view update, but cannot fence an IndexedDB transaction or
attribute an old queued command. Server authorization remains authoritative and
cannot retroactively identify the author of an unattributed local envelope.

A full replacement needs both identity-bound local repositories and an
authoritative complete baseline with ordered change-feed handoff. Introducing
only the former in the live application would block existing workflows without
providing a safe replacement working set.

This ADR accepts an **additive, isolated Dexie v5 factory and local kernel**. The
production `App`, default `OcwpDatabase` singleton and existing Golden Slice
continue using the v4 path without activation of this kernel. Their pre-existing
shared-cache, cross-user replay and offline permission-freshness risks remain
open. Passing isolated tests does not qualify the live UI for shared-browser
multi-user operation.

Traceability: Foundation ADR-003/007/013 and TA-02/05/07; Security/Privacy §§8–10,
18 and 21; FR-IAM-002/004/006/008; OFF-001/003/005–009/012; NFR-004/005/010/014;
SEC-002/003; and QA INV-LOCAL-001/GATE-LOCAL-001. Future user-facing integration
must also satisfy ACC-002/003/004/008/010. This preserves AGPL-3.0-only, DCO,
Offline First, Local First and server-enforced least privilege.

## Decision

### 1. Explicit unactivated boundary

The isolated modules live under `apps/web/src/access-kernel/`: `types.ts` defines
local records/tickets, `context.ts` handles pure context validation/state,
`operations.ts` handles canonical envelopes/result validation, `projection.ts`
composes explicitly labelled pending/unconfirmed views, `database.ts`
provides `createKernelDatabase(name)`, and `kernel.ts` exposes `AccessKernel`.
The v5 factory requires an explicitly selected isolated database. It is not the
application singleton and must not upgrade a user's production `ocwp` database
as an incidental import or test setup step. The kernel consumes context metadata
through an explicit local boundary; that metadata is not authentication proof.

New contexts stop at `BASELINE_REQUIRED`. No login, matching user ID, empty queue,
old numeric cursor or zero-cursor replay establishes a complete authorized
working set. There is no fallback to legacy data. Test fixtures may establish
ready state to exercise repository invariants; they do not prove a server
baseline or provide a production activation procedure. `READY` is reusable only
when the same verified context already has a matching completed partition. This
increment provides no baseline merge/activation API or HTTP adapter; tests seed
that future-integration prerequisite directly.

This increment introduces no `/auth/context` endpoint, baseline/delta endpoint,
new wire contract, server migration, credential, bearer-token persistence or
production login/coordinator wiring. Authentication-context validation, complete
baseline production and integrated expiry/reconnect UX are later work.

### 2. Context and durable transaction fencing

Keep the principal (API realm, organization and user), concrete selected
location, authorization epoch, partition and durable device generation distinct.
A role label, matching organization/location or mutable global token cannot
replace the captured principal. A context ticket is local routing/fencing
metadata, never a credential or a server authorization grant.

Repository operations validate their ticket and relevant capability inside the
same IndexedDB transaction as their read, journal/projection write or delivery
update. One active context generation per database fences old tickets across
kernel instances. A context switch or lock changes durable control state before
new work can proceed. A late response cannot commit against a superseded ticket,
advance another context's progress or acknowledge its operations. Broadcast or
React guards, if added later, are responsiveness aids rather than correctness
boundaries.

Operational reads require explicit entity read capability. Write-only access
does not expose cached records, order-event evidence or conflict details.
Unknown entity types and mismatched scope fail closed. Kernel isolation is
logical application isolation; arbitrary direct IndexedDB access is outside it.

### 3. Immutable authored operations, separate delivery history

New journal entries capture their original principal, organization/location,
authorization context, stable local sequence and original v1 mutation envelope.
The journal and event history reject updates/deletion through the database adapter,
in addition to the append-only kernel repository API. Mutable delivery
status and append-only result/attempt history are separate records. No token or
password belongs in any of these records.

A command's journal entry, initial delivery state and local event evidence must
commit atomically. Confirmed cache records stay separate from pending work; a
refresh must never overwrite the only copy of a local command. Read composition
and dispatch only use the current author's eligible work in the original realm
and workshop. No author transfer, automatic rebase or regenerated mutation ID is
permitted. Dependencies and per-entity ordering must preserve parent outcomes;
holding one chain must not discard unrelated operations.

Acknowledgement changes delivery state, never deletes the journal's original
payload. A conflict/rejection retains the complete envelope and history. Retry
and lost-acknowledgement recovery use the original operation ID and unchanged
payload/base version. An entity's existence or higher version does not prove a
particular queued operation applied. A future explicit resolution must be a new
operation linked to preserved history, not a rewrite of the rejected command.

An applied ACK does not fabricate a server projection. Until a validated
confirmed version covers it, the read model retains the author's local overlay
with `optimisticStatus: applied_awaiting_projection`. It yields to authoritative
projection data when that version arrives. Old-epoch work remains immutable and
can be composed/replayed only for the same author/scope under the current verified
capabilities and completed baseline; explicit dependencies and implicit earlier
aggregate commands are followed transitively. Rejected/held chains stay hidden
from the operational overlay while their evidence remains available through the
read-gated journal API.

Dispatch scans at most 100 candidate delivery-metadata rows per call, using an
indexed author/scope/eligibility/local-sequence range and a durable scan position
that wraps/revisits deferred work. Numeric eligibility flags are valid IndexedDB
key components. Indexed earliest-unresolved aggregate checks preserve ordering,
and attempt/generation indexes validate batch membership without origin-wide
inflight scans. Applied/rejected lifetime payloads are not scanned during normal
dispatch. Projection reads query pending metadata in reverse pages of at most 100 rows
and the latest applied version beyond confirmed coverage, loading needed
immutable payloads lazily. Older pages remain eligible when newer chains are held;
large unresolved backlogs and dependency graphs still need the separate device
performance qualification. No journal garbage collection is introduced.

The dispatcher captures its context and batch. Result validation checks requested
mutation IDs, entity identity, status/schema, plausible versions and captured
scope/operation consistency before any acknowledgement transaction commits.
Unknown, contradictory duplicate, mismatched or malformed results must not
partially acknowledge the batch. A stale fence rejects the response. Delivery
history retains the outcome without pretending a network failure proves the
server did not commit.

These local controls do not strengthen the existing server receipt into proof of
original actor or complete payload equality. Receipt actor/digest binding and
its legacy-data policy remain a separately reviewed security prerequisite.

### 4. Additive v5 and lossless legacy preservation

All eight existing v4 stores, their records and existing indexes remain intact:

- `customers`
- `mutationQueue`
- `syncState`
- `conflicts`
- `bicycles`
- `serviceOrders`
- `serviceOrderEvents`
- `presentationPreferences`

The isolated v5 layout adds these eight stores:

- `deviceControl`: durable active-context generation and local control/sequence
- `accessContexts`: principal, concrete scope, epoch and offline deadline
- `cachePartitions`: partition metadata, baseline completion and opaque cursor
- `cacheRecords`: partition/type/entity-keyed confirmed projections
- `operationJournal`: immutable author-owned original commands
- `operationDelivery`: mutable per-operation delivery/attempt state
- `operationEvents`: preserved operation evidence and delivery history
- `localMigrationState`: local schema/legacy-preservation metadata

It does not rekey, copy into an assumed user's partition, normalize, relabel,
clear or automatically replay legacy rows. Existing unknown fields, queue
states, conflict payloads and order events must survive unchanged. Legacy sync
cursors are never adopted as a new context's baseline checkpoint.

Every legacy queue row remains unattributed, including rows with an apparent
actor field or matching current organization/location. Neither a login nor a
presentation conflict-type marker proves historical authorship. The isolated
kernel exposes no claim/replay shortcut. Recovery notices must be non-sensitive;
one user must not receive another user's legacy payloads merely by signing in.

Personal appearance keeps its organization/user key; the device-local logo keeps
its organization/user/location key. The kernel neither resets nor shares these
records. No logo upload, shared branding or new credentials are introduced.

Migration is local and additive. Transaction failure must roll back the upgrade
without deleting the old database. Preservation tests must compare exact values,
including unknown fields, across supported raw native-v1 and logical Dexie
v1/v2/v3/v4 fixtures; counts alone are insufficient. Physical native-version
fixtures and real-browser execution must be identified explicitly in evidence.

**Observed old-bundle blocker:** Dexie 4.4.4 with the IndexedDB emulator allows
an existing v4-only `OcwpDatabase` instance to open a native50 database and write
the legacy queue. A negative test expecting a lower-version rejection failed;
the retained regression records the actual unsafe compatibility behavior. A
separate native-browser journey must verify this result on hosted Chromium.
Schema version alone is therefore not a writer fence. Before activation, review
an isolated new database name together with explicit service-worker/client
protocol fencing and a no-mixed-writers installation procedure. These are future
architecture options, not implemented mitigation or a claim that a hostile old
same-origin bundle can be made trustworthy. Production remains untouched here.

The unimplemented quote-local-store reservation moves from **v5 to v6**. This
supersedes the reservation in the structural-theme ADR/plan, not an applied
migration. Future v6 work must preserve the v5 journal, context/cache records and
personal preferences. Reinspect the integrated schema before implementing it;
never overwrite a version that has actually landed. Administration Alembic
`0008` and future quote PostgreSQL `0009` remain unchanged. No empty or fractional
reservation migration is created.

## Production activation gate

The following are prerequisites, not capabilities delivered by this increment:

1. A server-validated effective context bound to user, realm, concrete workshop,
   current session, effective grants, authorization policy and bounded offline
   deadline. Reconnect revalidation must precede dispatch; no offline expansion
   of identity, scope or privileges and no silent raw-account fallback.
2. A complete authorized baseline, including historical records created through
   direct REST paths, plus ordered delta continuity. An empty queue or replay
   from numeric cursor zero is insufficient. All supported writers must emit
   changes atomically and obey the same commit-order barrier, proven on real
   PostgreSQL with delayed writers, rollback gaps and revocation races.
3. Private bounded staging, validated page/cursor transactions, version-dominance
   merge and atomic final activation. Grant expansion requires backfill;
   contraction cannot restore an older broader view after failure. Preserve each
   author's pending work independently of baseline records.
4. An integrated replacement of production auth, repositories and sync together
   with the v5 singleton. Keep the existing production path unchanged until that
   replacement and its safe compatibility/recovery procedure are qualified.
5. Exact-final-head production PWA/IndexedDB evidence for same-workshop A/B
   switching, delayed commits/ACKs, multiple tabs, offline reload/reconnect,
   permission changes, storage pressure and upgrades. Preserve the Golden Slice
   outcome. Its historical v4 legacy-replay fixture may only be superseded at
   activation by stronger preservation/non-replay coverage and separate
   known-author unchanged-ID replay coverage, never silently weakened.
6. Old-bundle/service-worker handling, blocked versionchange UX, compatible
   rollback/forward repair and an explicit operator policy for legacy pending
   work. A v4 writer must not continue alongside activated v5 writers. Future
   restore/redeployment must invalidate incompatible sessions/checkpoints;
   automatic server dataset-restore detection is not implemented here.
7. Review the remaining server receipt actor/payload-binding risk explicitly.
   If the deployment requires that guarantee, qualify its migration and legacy
   policy before rollout. Qualify concrete-workshop selection before enabling
   organization-wide owner navigation or the administration UI.

Real-browser and PostgreSQL evidence are independent gates. Unit tests, fake
IndexedDB, static checks, historical hosted results, ARM64 image builds or this
ADR do not close physical Windows/Android, accessibility, installation or broader
release-security gates.

## Recovery and operator boundary

No actual installation upgrade, legacy recovery or deployment is performed by
this increment. A server backup does not contain a browser's unsynchronized
queue or journal. Do not clear IndexedDB, uninstall the PWA, change origins or
downgrade schema as a routine recovery step.

For a future affected installation, preserve the original database and verified
server backup, pause affected dispatch, establish provenance privately and
separate possibly-applied commands from never-sent work. The current server
receipt cannot establish historical ownership or complete payload equality.
Recovery requires an authorized, reviewed history-preserving procedure; it is
not a button that silently assigns all old work to the current login. A deliberate
new submission by another actor needs a new audited action linked to the
preserved original. Missing payload/provenance must not be guessed.

On upgrade blocking, quota failure, ambiguous acknowledgement or an invalid
context, preserve data and surface an actionable hold. A compatible forward fix
is preferable to destructive downgrade. Any export/access to preserved private
data needs an explicit recipient and security design. The operator gate for
legacy pending work does not require deleting it before an independent user can
receive a newly authorized baseline.

This is not encryption, remote erasure or protection against a device owner,
same-origin malicious script or compromised browser/OS. Device security and the
unavoidable offline revocation window remain explicit residual risks.

## Evidence

Implementation, regression red/green, migration, static, aggregate, independent
review and any hosted/browser results are **pending** until recorded for the
actual tested source in the
[increment record](../10-spec-development/2026-10-14-isolated-offline-identity-kernel.md).
The Node suite uses real Dexie with the `fake-indexeddb` emulator; this is not
real-browser evidence. A dedicated browser harness must have its execution and
results recorded separately. No activation, PostgreSQL, hosted or physical-device
evidence is implied here.
