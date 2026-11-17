# Capture transition: inert custody before operational handover

Status: **Proposed**, not an accepted production transition or deployment decision.
Baseline: PR110 main `ffa51bbe42c1108da2c198379c4f97eac9ef2508`.

## Decision requested and recommendation

Keep current shared-origin v1 writes unchanged. Recommend evaluating a fresh protected
origin with an exact compatibility-aware artifact floor, as PR110 proposed, but do not
choose a production domain, entry point, authentication bridge or migration here.
A technical snapshot cannot revoke an offline historical writer. Therefore an import
must not become a live capture merely because its source was unchanged during a check.

Build the next prerequisite as **inert custody**, distinct from operational restore:
read an admitted synthetic source coherently, retain a complete bounded v1 draft in a
separate test-only database, read it back exactly, and observe subsequent source change.
The staging database has no operational tables, dispatch adapter or promotion API.
The prototype cannot enroll a capture, submit a command, delete source data or transfer
exclusive ownership. No credentials or remembered-session markers cross this boundary.

## Deliberately conservative eligibility

This first prototype handles open exact-v1 checkpoints with at least one valid UNSENT
channel and otherwise EMPTY channels. Unsupported, PROTECTED, UNAVAILABLE, expired,
closed, mismatched or malformed state refuses. Both original payloads, generation,
revisions and absolute TTL remain intact; no interpretation of future intent occurs.

**Any journal, delivery or operation-event record refuses this prototype**, even applied
history. This is stricter than merely rejecting pending work. It avoids claiming that a
partial command/history migration can safely preserve dependencies or unknown receipts.
It is not a production limitation decision and does not clear those source records.
A real pilot with history cannot use this prototype as its migration tool.

## Concurrency and privacy contract

A single source transaction reads the capture, control, admitted context/partition and
presence of operation work. Current identity/scope and writer metadata must match.
The detached bundle includes a portable owner routing tuple and exact checkpoint/content
bytes, but not credentials, session binding, context grants or command payloads. The
owner tuple and caller admission checks are synthetic routing gates, not authentication.

A transfer ID permits identical retry only; different bytes conflict. Staging and
readback happen atomically. A failed write, quota abort or session invalidation cannot
acknowledge custody. A second coherent source observation detects edits, protection,
work appearing, session change or expiry. Even `source_unchanged_at_check` is only an
observation: a writer can change the source immediately afterward. All staged results
remain `operationalUse: forbidden`.

Reading custody checks its complete shape, exact owner, content correspondence, size,
clock and original expiry. Expiry refuses access without silently purging data. The
synthetic test owner deletes only its own disposable database during test cleanup.
There is **no production retention/logout/cleanup mechanism** for custody in this PR;
that unresolved privacy policy prohibits real-data use or integrating it into the App.

## Tradeoffs and remaining decisions

Custody provides recoverable evidence and detects drift without risking duplicate
submission. Its cost is that it intentionally does not complete the user workflow.
Promotion needs a separately reviewed authority protocol: reconcile newer source edits,
resolve journal/PROTECTED/unknown work, reauthenticate both endpoints, define concurrent
source-write handling, verify destination identity/dataset and maintain source recovery.
A point-in-time check, epoch flag, disabled button or service-worker refresh cannot be
substituted for that protocol.

Before production implementation, decide whether old unsent work must finish at source
or undergo explicit conflict-aware transfer, define supported artifact/rollback entry
points and temporary-copy privacy policy, then qualify actual browser/physical recovery.
No accepted ADR is superseded. G1–G6 remain open; this prototype is a G3/G4 prerequisite,
not their closure, and does not activate existing-bicycle selection or any new format.
