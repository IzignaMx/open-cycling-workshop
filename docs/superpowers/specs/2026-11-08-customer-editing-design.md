# Existing-customer editing: explicitly memory-only unsaved input

Status: current user-selected design; locally verified, hosted/browser
qualification pending. Base `463ac45d39812f3b4d92e5066b9e40ee6c598e67` (PR95).
FR-CUS-003/R02-T001 remains a bounded independent prerequisite, not full V0.2.

## Explicit decision and scope

After reviewing durable editing compatibility risks, the user chose option 1:
edit name, email and phone without retaining unsaved editing drafts across sessions
or interruptions. The user also clarified that no versions are installed or in
production. Previous-version enforcement is separate research, not authorization
to add persistent edit drafts or an implementation prerequisite for this slice.

This explicit choice narrows UX§22 recovery for unsent edits only. Existing durable
customer-creation and order drafts retain their current 24-hour expiry and logout
policy. Do not remove their recovery, clear IndexedDB or modify existing journals.
No automatic submission or replay follows from restoring the application.

## Current architecture and invariants

The `customerEdit` presentation owner holds only the current uninterrupted editing
view in memory. Customer identity, original field values and opening version never
become a new persisted draft, checkpoint channel or sessionStorage entry. Masking,
re-admission, logout, scope change or reload drops this volatile editing input and
invalidates stale handlers. Explain the limit in the editor; same-screen dirty
cancel/leave needs explicit discard. No silent autosave or hidden recovery claim.

A submitted, positively committed update is different: it enters the existing
immutable local mutation journal, remains durable and synchronizes normally even
after reload. The editor never deletes business history when closing or cancelling.
An unknown result prevents another submit in that live view. After interruption
there is no draft to replay; actual committed commands remain in the journal with
their original IDs. Do not infer rollback from a missing success message.

Use existing authenticated runtime/kernel/scoped repository. Identity,
organization, location and creation time are immutable. Save uses captured
`base_version`; a newer projection must not silently rebase the edit. Admission
requires current customers.read/customers.write authority. The kernel rechecks
version and blocked customer aggregate state inside the existing transaction,
after exact-ID replay handling. Scope/capability loss, pending conflicts and stale
callbacks cannot leak fields into a new view or append an unsafe overwrite.

Name/contact normalization and limits share the established customer rules. NUL
and unpaired surrogates are rejected before durable enqueue; valid astral Unicode
is preserved. HTML maxlength must not silently truncate by UTF-16 units or count
raw input differently from normalized codepoint limits. Local saved, synchronized,
conflict and unknown are distinct outcomes.

No backend/schema/wire, dependency, authenticated IndexedDB version/store,
checkpoint format or creation/order recovery change is selected. No new general
store, API route, financial operation or constitutional architecture change.

## Required verification and limits

Observe RED before the memory-only behavior and retain tests proving unsent edit
values are absent from all local stores/sessionStorage, disappear on interruption
and never auto-submit. Prove saved update durability, actual committed-but-lost
acknowledgment, single-flight, cancellation, stale scope/view, version/conflict
races, denial of blocked aggregates and valid Unicode. Existing capture recovery
and migration tests must pass with original code restored byte-for-byte.

Isolated real-API Playwright cases cover unsent-input loss, saved offline updates
through reload/reconnect, cancellation/read-only denial and competing server
conflict. Collection/typecheck is not execution. Full frontend, static/build,
repository and available aggregate checks are required before local completion.
Native browser/PostgreSQL remain environment-limited; hosted acceptance belongs
to a separately authorized published candidate.

## Rejected historical experiments

The uncommitted in-place v9 channel extension let unchanged old-v8 maintenance
delete valid synthetic draft rows. A dedicated-sidecar alternative would delay
old-client logout cleanup. Neither was published or deployed; the user reports no
installed prior versions. These are preserved synthetic design findings, not a
production incident. The unsafe schema/channel changes were removed; the current
memory-only choice does not weaken the existing persisted-draft privacy policy.

Physical T1–T8/R01-T035, capacity/M2, real restore, deployment, quote activation and
full V0.1/V0.2 acceptance remain outside scope. Publication is not authorized.
