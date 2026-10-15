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

## Offline reload startup completion follow-up

The first published refresh correction, head
`93b9b30e09fa90c9dffc78105b8ef5fbc172852d`, tree
`cb938f964b990d878403ce0ab9a1491f8f7cc270`, made progress but did not complete
qualification. In [CI38678325955](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38678325955),
the direct browser result was again **62 passed, one failed, zero flaky**.
Both attempts passed the previous verified-offline-copy assertion at line487,
then reached ready state after the first reload and failed `expectBrand` at
`branding.spec.ts:494`: the accessible identity was `OCWP, taller activo`
instead of the saved workshop brand. This later failure is distinct from the
retained before-reload failure above.

[Direct artifact11947607520](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38678325955/artifacts/11947607520)
ZIP SHA-256:
`91eb05eff5ff579b67652b871b06b5465e2e7247a1d332976c90e73aca7cd270`.
The aggregate result was still pending at this local correction checkpoint;
repeat phases had not executed. Neither the earlier source fixes nor local
composition tests are claimed as a completed browser journey.

### Reload cause and bounded correction

Both `start()` routes (navigator-offline and online-hint followed by a genuine
network failure) reach `resumeStoredOffline()` and `ready(..., false)`.
`ready()` publishes ready state, starting the branding cache read, before its
initial customer/order/issue reads. These real kernel transactions update
`deviceControl.observedAt`. The conservative cache correctly rejects an older
operation-entry timestamp. Unlike the explicit offline transition, startup had
no completion refresh request, and same-binding publications did not restart it.
The former fixed-clock reload fixture masked this interleaving.

After the existing initial operational `refresh()` completes, offline startup
now requests one forced branding refresh only if the same source remains active
and current. This uses the existing one-initial/at-most-one-trailing budget and
fresh admission/time capture. The coalescer and cache implementation are
unchanged. No null-result retries, extra timers or connected-startup requests
are introduced. Later independent writers can still fence a read; the change
closes the known startup completion gap, not every possible future interleaving.

### Reload evidence

Exact Node22.16.0, installed dependencies, real production controller/kernel/cache
with fake IndexedDB and controlled transport:

- **RED: three failures, nine negative controls passed** on the prior product.
  Both complete stored-session restart routes fail with advancing clocks; a
  third controlled failure holds the actual logo digest while the initial
  customer page executes its real kernel transaction at a later timestamp.
- **GREEN: twelve focused cases passed** after the three-line production change.
  They include the two restart routes and delayed-logo success; rollback,
  expiry, takeover, logout and a future snapshot remain closed. Four additional
  cases interrupt startup before its initial page returns and prove no stale
  completion request after logout, takeover, expiry or session replacement.
- Tests perform connected admission, confirmed logo caching, offline transition,
  pending customer creation, disposal, new controller/database-handle startup
  and actual remembered-admission owner replacement. Snapshot bytes, pending
  journal and delivery records remain identical. Offline-only startup makes no
  network call; the online-hint fallback makes only its failing `/auth/me` probe.
- Independent diagnosis reproduced the exact null-cache mechanism and confirmed
  that one explicit request after startup restores branding without durable
  changes. The browser artifact does not identify its exact interleaved writer;
  the controlled production-composition tests prove the source mechanism.
- Full frontend core: **764 passed, zero failures or skips**. Repository
  contracts: **22 passed**. Touched ESLint/Prettier, web/offline typechecks and
  production PWA build passed; the existing large-chunk warning remains.
- Independent isolated review passed **130 committed-scope cases and nine
  additional reviewer probes**, overlapping the full suite rather than adding
  browser journeys. The probes include three consecutive stored-session
  startups with real logo, light/dark preference saves, advancing clocks and
  new owner generations through both startup routes, plus the retained queue,
  binding, latest-profile and adverse-time controls. Durable branding, journal
  and delivery rows remain unchanged.

Fresh exact changed-head hosted direct/aggregate browser and retry-free repeated
journeys remain required. No native browser, physical device or deployment pass
is inferred from this local evidence.

### Subsequent aggregate evidence and connected completion

The previously pending aggregate of CI38678325955 finished with **26/27 controls,
2375 Python passes / 14 skips, 752 frontend passes**, and **60 first-pass browser
cases, two flaky retry passes and one final failure**. The final failure remains
the offline reload above. Two additional first-attempt failures rendered OCWP
instead of current branding after connected relogin and connected preference
reload. Both passed retry1. They are not covered by the offline-only completion
request. The [separate connected follow-up](2026-10-15-connected-branding-refresh.md)
records their artifacts, deterministic cause and bounded first-sync correction.
The earlier local offline commit and its evidence remain retained.
