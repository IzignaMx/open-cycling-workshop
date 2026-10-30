# Safe feedback for existing order transitions

Assistant-selected bounded design under delegated technical decisions, not a
claim of human approval of this document. Baseline main
`b393c58b1f6551b77e657372d70e0eb2af51f522`, tree
`243e19f47dbdb114f1c58a6ac12849be076d175a`.

## Intent and source boundary

Remove arbitrary exception text and accidental repeated activation from the
existing order board. Preserve the existing repository/kernel atomic order,
timeline and mutation-journal write, state machine and server conflict policy.
This is maintenance of existing functionality, not new module execution or a
new domain API. Relevant requirements: OFF-003/005/006/008/009/012,
ACC-001/002/004/008/010, AC-UX-011 and the master loop's error/privacy rules.

`OrderList.tsx` currently renders `Error.message` and relies on asynchronous
React busy state. `runtime/repositories.ts:transition` resolves only after the
existing `commitLocalCommands` call. Its rejection does not establish rollback:
a native commit can precede promise rejection or a failed postcommit fence.
The capture-only proven-abort mapper must NOT be reused here.

`controller.ts:transition` subsequently refreshes the view and timeline.
`refresh()` can swallow a read error by placing the session on hold; calling
`timeline()` afterward can throw or reacquire a replacement session. Neither
failure reverses the earlier commit.

## Alternatives and selected scope

1. Sanitize messages alone: does not prevent same-tick double activation or
   distinguish committed work from unavailable follow-up reads. Rejected.
2. **Selected:** a closed controller result and synchronous per-order gate owned
   by the existing mounted OrderList, above filtering. It survives card removal,
   filtering and pagination while that list remains mounted, with no new storage.
3. App/controller session-owned gate: could survive same-session reconnect but
   requires additional owner/reset/reconciliation semantics. Deferred rather
   than silently introducing an in-memory recovery ledger or stronger guarantee.

The selected gate is explicitly volatile. Full workspace unmount, including
automatic reconnect verification, reload and other tabs are outside its lifetime.
It is NOT durable duplicate prevention or proof that an uncertain operation did
not commit. Do not describe reconnect as reconciliation or invite replay.

## Controller contract

`transition(orderId, action)` returns a fresh closed result:

- `{ status: 'committed', view: 'updated' }`: existing repository fulfilled and
  normal follow-up reads completed while the exact captured source remained
  current. This does not certify server synchronization, complete remote history
  or physical durability.
- `{ status: 'committed', view: 'unavailable' }`: repository fulfilled but the
  source changed, refresh held the session, or follow-up reads failed.
- `{ status: 'unknown' }`: repository/preparation did not positively fulfill.
  No reason, arbitrary cause, input value or exception is exposed.

Capture source once. Recheck exact active-source identity and its current fence
after repository, refresh and timeline awaits. Never start timeline or wake
sync against a replacement source. Once repository fulfillment establishes
commit, no subsequent failure may downgrade it to unknown or not-saved.
Existing refresh hold behavior and timeline's bounded remote fallback remain.
No transition result authorizes retry; no `not_committed` variant is added.

Positive availability is explicit, not inferred from a resolved promise:
`refresh()` returns a boolean after its current-source publication, false on
hold or stale-source exit. An internal captured-source timeline helper likewise
returns false on missing authorized order/stale source and true only after
publication; the existing public `timeline(orderId): Promise<void>` wrapper
retains its interface. No source replacement may be reacquired inside that helper.
Require exact `true`, not truthiness or undefined. Remote-history fallback still
provides an available local/partial view; it does not prove remote success.
Existing capture callers retain their saved-result behavior when refresh returns false.

## Presentation and gate

Use fixed Spanish feedback, defensively decoding the closed result. Rejection,
unknown/extra fields, hostile getters or malformed values yield UNKNOWN without
echoing any input. Committed/unavailable says the change was saved locally but
the view could not be updated; it must not suggest repeating the action.

The list-owned gate acquires an order ID synchronously before invoking the
callback. Busy React state is only presentation. Other orders remain independent.
Pending, UNKNOWN and committed/unavailable disable that order's action buttons.
Only positively committed/updated releases it for a later explicit action.
Never release uncertainty in `finally`, on callback replacement, order version
change, a different action, filtering, pagination or a timeline click. There is
no automatic retry or new unblock/recovery control. Existing read-only history
and search remain usable. Render feedback accessibly with no raw error echo.
Late completion belongs only to its original mounted gate, never a replacement
list. Losing a gate on unmount is a surviving limitation, not evidence of
noncommit; new workspaces still require all existing authentication/read fences.

## Evidence before completion

- Deterministic RED/GREEN: same-tick exclusion, independent orders, pending and
  uncertain filtered-card remount within the same OrderList, changed row/callback, hostile results/errors,
  explicit subsequent action only after committed/updated.
- Actual repository/controller: ordinary offline commit; rejection before write
  and after a real synthetic commit; refresh failure/hold; timeline failure;
  source replacement during each await; unchanged journal/event/projection and
  no replacement-source reads or stale sync wake.
- Actual PWA browser cases: real order board, synthetic prewrite failure and
  postcommit follow-up failure, fixed messages, retained work, no repeat after
  filtering, keyboard and axe. Local absence of pinned browser/API/PG is not a
  passing browser result; require fresh exact-source hosted artifacts.
- Retain all prior suites, budgets and controls. Independently review final
  patch, run static/build/offline checks and full hosted qualification, then
  fresh postmerge proof before marking implemented scope verified.

## Separate readiness gates

V0.1 remains partial: physical Windows/Android R01-T035 is separate from quota/
eviction, screen-reader/touch, installation/recovery and quote activation gates.
This slice cannot close those gates. M0 remains a data-only descriptor contract;
no loader, extension trust, grants, routes, schema/store, dependency or deployment
is introduced. Pages remains at deployed source `3c6513d`. Ownership measurement
40927223929 remains permanently spent; no repeat or identity rotation.
