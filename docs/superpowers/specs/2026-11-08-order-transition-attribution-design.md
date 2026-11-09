# Order transition attribution in the existing history

Status: bounded implementation locally verified and reviewed; hosted qualification pending.
Base main is `3534fdd59f219bdcd4943aded4b86f7883b0d382` (PR96).
This is a partial FR-SVC-016/R02-T013 increment, not complete staff assignment.

## Purpose and non-goals

The user requested continued work toward a multi-user cycling workshop, including
visible authorship. Expose the existing transition's full `actor_id`, its recorded
`occurred_at`, and its source in the same order-history view. Label the identifier
**Autor (ID)**, not an assigned mechanic or resolved personal name. No IAM lookup,
new endpoint, capability, migration, persisted event field or wire change is needed.
Assignment remains separate FR-SVC-004/FR-STF-003 work.

## Evidence and provenance

The server uses authenticated actor context, not a payload's claimed actor. A
direct HTTP transition uses the server domain clock, but a synchronized transition
preserves the original mutation timestamp. Therefore **Fecha registrada** is not
proof of server-clock time, event ordering or confirmation.

The admitted local history contains this author's original operation events,
including historical rejected/conflicted/applied attempts. Local does not mean
pending and must not be presented as server acceptance. A baseline contains order
projections, not complete historical events. Keep existing partial/offline notices.

Use an ephemeral `recordSource` discriminant added after the authorized read:
**Registro local** versus **Registro del servidor**. The read path owns this value;
an event's stored fields cannot choose its provenance. This projection never writes
back into the journal, local event store, database schema or API payload.

## Composition and presentation

Keep the existing `event_id` merge semantics: local rows replace matching remote
IDs, and distinct IDs remain distinct even if actor/action/time look identical.
Server-generated IDs may differ from a related local attempt; no deduplication or
operation-to-event linkage is invented. Preserve lexical ordering for valid
timestamp strings. A malformed non-string timestamp uses a safe empty comparison
key rather than throwing; no original value is normalized or rewritten.

Render the full bounded identifier as inert text, with a safe unavailable fallback
for malformed/missing values and control/format characters. Isolate valid RTL
identifiers with `bdi` without changing the recorded value. Do not derive an author
from the current session.
Use semantic time markup only for valid explicit-zone dates, retaining recorded
precision and timezone. Do not infer UTC from missing timezone, normalize invalid
calendar dates, show Invalid Date, or render raw objects. Invalid/ambiguous values
have an explicit unavailable fallback. Long identifiers must wrap accessibly.

No additional reads, mutation dispatches, grants or changes to state transitions
are introduced. Existing readable-order, tenant/location, current-session and
capability fences remain the authority for what reaches the component.

## Verification

Observe RED before implementation for rendered actor/time/source and runtime
projection. Use the real OrderList rendering, not native substitutes that can hide
component forwarding defects. Cover two authors, exact IDs, timestamp precision,
zone/calendar edge cases, hostile text, missing fields, source spoofing, collisions,
distinct duplicate-looking records, immutable input and retained journal history.

Exercise local history after reload, rejected attempts, remote failure, stale
sessions and read scope. Extend the isolated native browser journey to inspect
visible author/time/source, while retaining exact version/journal assertions.
Authored/collected Playwright tests are not browser execution. Final local checks,
independent review and any later hosted qualification remain distinct evidence.

Physical T1–T8, M2/capacity, deployment, real-data restore and complete audit/staff
acceptance remain out of scope. Publication requires new specific authorization.
