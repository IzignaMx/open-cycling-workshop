# Session-bound local sync wake · 2026-10-16

## Failure and evidence boundary

QA54 direct browser artifact **12054078215** retains the failed first attempt of
`raw v1 legacy evidence and late old-tab additions remain exact, unknown and never replayed`.
The retry passed; that does not qualify the first-attempt browser gate.

Observed sanitized trace facts:

- Reload's ordinary delta started at `15:00:30.124Z` and lasted `384.941ms`;
  HTTP 200, phase `complete`, zero records, completion present.
- Save click ran `15:00:30.166–30.207Z`; local-save feedback was visible by
  `30.265Z`; the journal predicate passed by `30.276Z`, and its final read
  completed at `30.289Z`, before the delta response completed near `30.509Z`.
- No mutation HTTP request was sent, and there was no later API traffic before
  the unchanged 15-second applied-acknowledgement predicate failed with `pending`.
- The admitted workshop showed local pending work. Legacy evidence equality
  had passed before the new operation; neither legacy mutation was replayed in
  the observed traffic. Assertions after the failure were not executed.
- Fixture identity creation and browser authentication/context requests succeeded.
  CI used one worker and a new synthetic principal per case/retry. The reason
  this delta took 385ms is unknown; shared-service load could influence timing.

The trace does not expose private timer callbacks. The internal lost-wake ordering
is inferred from those observations and the controller: push inspected an empty
queue, delta awaited, local commit requested sync while the controller was busy,
and the idle tail selected its 30-second poll. A deterministic held-delta test
reproduced missing automatic dispatch on the unmodified controller before this fix.
This is a product scheduling defect exposed by a valid READY-state write, not a
reason to wait for idle sync before allowing users or tests to commit local work.

## Bounded correction

Only successful local customer/order/transition commits request the extra wake.
The caller captures its original active source and network generation before
awaiting storage and refresh. A busy controller retains one coalesced wake for
that source/generation; a successful current cycle consumes it after releasing
its running flag. Normal polling and repeated manual sync calls do not create
additional wakes. Kernel dispatch remains responsible for authorization,
identity, dependencies, immutable mutation IDs, and delivery state.

Cancellation, replacement session/workshop, held admission, disposal, and offline
transition invalidate the wake. A stale cycle cannot consume a newer source's
wake. The wake is not drained after retry, offline, failed refresh, or invalid
admission outcomes. Existing retry scheduling remains separately authoritative.
The pre-existing mixed-outcome branch ordering (progress/applied before retry)
is not changed by this patch. Controlled-clock comparisons observe one immediate
cycle with or without a local wake in both applied/retry and retry/progress cases.
Awaiting that cycle confirms that the failed delta request and failed mutation ID
are not resent before their durable retry deadlines. An extra scheduler cycle
is therefore not evidence of an HTTP backoff violation.

No legacy queue, evidence store, journal envelope, admission contract, browser
assertion, browser timeout, CI retry setting, or capacity-profile setting changes.

## Qualification boundary

Deterministic local tests cover the causal overlap, multiple commits, unchanged
IDs/journal, cancellation, replacement identity, offline, error, refresh overlap,
and stale-cycle completion against a newer session's pending wake. Controlled
clocks prove coalescing, quiescence, the ordinary idle interval, and retry deadline
preservation. The full local core suite passed **928 tests**, including eleven new runtime
cases; repository/CI contracts passed **27 tests**. Web typecheck, focused ESLint,
Prettier and clean-diff checks passed. Independent exact-package review remains
a separate pre-publication gate. Fresh exact-source hosted browser qualification remains open;
local tests do not replace that gate. The failed artifact and its retry history
remain evidence rather than being overwritten by a rerun.
