# Offline branding: preserve an explicitly requested refresh

Date: 2026-10-15. Status: implemented_pending_evidence.
Base local source: `19dcd926c96f975009a95b7726ae8e96cfa4319e`.
Scope: branding refresh scheduling and repeated-offline readmission. The cache
repository, six entry-time rollback regressions, browser assertions, timeouts,
schema, grants and operational mutation semantics are unchanged.

## Retained direct and aggregate failure

[CI 38676085071](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38676085071)
ran published head `d4c05100e83da06710e0843c6c2fd18447095e2b`, exact tree
`a57c700a764ec4f3aba322bfa763745f49b82358`. Direct browser evidence has **62
passing cases, one failing case, zero flaky cases**. Both attempts of
`verified brand survives offline reload while shared edits never enter the
journal` failed at `branding.spec.ts:487`, expecting
`Copia verificada disponible sin conexión.`. This occurs after switching
offline and creating a pending customer, **before the first reload**. The error
context shows a ready/offline workshop with the customer retained, but no
visible shared branding.

[Direct artifact 11946313686](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38676085071/artifacts/11946313686)
ZIP SHA-256:
`2ad2bb6799950a761b0881abd47ebfc3180df225e05178fe236ddc1b56586ce4`.
[Aggregate artifact 11947545007](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38676085071/artifacts/11947545007)
ZIP SHA-256:
`11dc5f486ac08c95f8d37452264746ee0e95d8873de573ca6c5d3cbb5ba377b2`.
Aggregate evidence also failed the same browser journey: **26/27 controls
passed, 2375 Python passes / 14 skips, 741 frontend passes, 62/63 browser
passes**. Repetition phases were skipped. These are retained failures, not a
retry-to-green result or a missing-browser-installation cascade.

## Cause

`offline()` publishes offline state before `continueOffline()` completes.
Publication reconciles branding and starts a refresh. That refresh validates
through the actual kernel, then reads the cache while other same-owner kernel
transactions can advance `deviceControl.observedAt`. The cache correctly refuses
an invocation whose immutable entry time is now older than trusted evidence.
The transition then requests `refresh(true)`, but the old single-flight guard
discarded it if the first read was still active. A null offline read left the
current binding without branding or scheduled recovery.

The browser artifact does not expose the exact interleaved writer. Deterministic
tests of the real WorkshopController, AccessKernel and cache reproduce the
mechanism with advancing wall/monotonic clocks, and separately with an actual
pending customer commit while logo SHA validation waits. Substituting only the
older pre-rollback cache makes the transition control pass, confirming that the
correct fail-closed change exposed the caller's lost recovery request.

Review also reproduced a second defect in the same flow: an already-offline
notification cleared branding, checked its lease and returned without
reconciling. This is recorded separately, not asserted to be the observed CI
writer/interleaving.

## Bounded correction

- Coalesce explicit forced requests received by an active initial flight into
  **one** trailing flight. Repeated requests do not create extra flights.
- The trailing flight cannot queue another: each busy cycle has at most two
  flights. Keep flight ownership installed during completion notifications so
  listeners cannot bypass that budget. Old finalizers cannot erase a replacement
  flight.
- The trailing call captures the current source, validates the kernel and takes
  a fresh wall timestamp. Clear/logout, stale binding, invalid admission and
  expiry cancel work. Existing newer-version memory cannot be replaced by an
  older queued response.
- A null cache result alone never retries. In particular, elapsed performance
  time cannot automatically wait out a future snapshot timestamp.
- After the already-offline branch's existing lease check, reconcile branding
  again. All cache checks remain in place; no cached bytes become authority.

## Local evidence

Official checksum-verified Node **22.16.0**:

- Three real-composition regressions fail on the previous product and pass on
  the correction: advancing-clock offline transition, repeated offline event,
  and actual pending customer work during a delayed logo digest.
- Four additional digest-race controls keep rollback, expiry, takeover and a
  future snapshot closed. Snapshot bytes and pending journal are preserved.
- Unit coverage proves fresh validation/time, a finite coalesced budget even
  with repeated consumer notifications, and cancellation on clear, invalid
  admission and stale source.
- Full frontend core: **752 passed, zero failures or skips**. The existing six
  cache rollback regressions remain included and unchanged.
- Repository contracts: **22 passed**. Touched ESLint/Prettier, web/offline
  typechecks and production PWA build passed through installed entrypoints.
  The existing large-chunk build warning remains.
- Independent isolated Node 22.16 review: **125 cases passed**, including seven
  additional reviewer-only race/security probes. This overlaps the committed
  suites and is not an additional count of product or browser journeys.

This proves real production composition over fake IndexedDB and controlled
network responses, not native browser execution. Fresh exact changed-head
direct/aggregate browser and the original retry-free administration repetitions
remain required. Physical devices, screen readers, operator installation and
deployment are not qualified by this change.
