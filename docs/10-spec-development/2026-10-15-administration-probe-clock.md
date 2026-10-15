# Administration probe clock fixture correction

Date: 2026-10-15. Status: implemented_pending_evidence.
Base: main `22b32a9e29f5b9dca9d52c2e8d36ac1228047c54`.
Scope: test clock initialization and qualification only. No production source,
timeout, probe deadline/backoff, credential assertion or runtime policy changes.
This describes the initial clock-fixture change. PR41 subsequently exposed an
independent production cache rollback defect; its bounded scope expansion and
retained original failure are recorded in the
[cache correction](2026-10-15-branding-cache-clock-rollback.md).

## Observed postmerge failure

[CI 38670900575](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38670900575)
[direct artifact 11944229438](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38670900575/artifacts/11944229438)
has ZIP SHA-256
`210380ed600acc4ac46a532c855b17baee41a6782ed4af2a6904baf96460f1a7`.
The direct browser report records **62 first-pass cases, one flaky case and
zero final failures**. The automatic-probe administration-secret case fails on
its first attempt at `page.clock.pauseAt(new Date())` with
`Cannot fast-forward to the past`; its retry passes. This is not a retry-free
63-case pass and does not establish a product secret-cleanup defect. The failure
occurs before the synthetic offline event, secret entry and probe assertions.

The preceding `clock.install()` starts a current-date fake clock. `pauseAt`
serializes a host timestamp before browser delivery. The installed Playwright
1.62 server and injected clock implementation reject that target if the running
browser clock has already advanced beyond it. A retry only changes timing.

## Bounded correction and causal regression

The fixture uses public Playwright APIs in this order:

1. Capture one target and `setFixedTime(target)` to stop wall-date advancement.
2. `pauseAt(target)`, which cannot consume a negative date interval.
3. `setSystemTime(target)` while paused to restore normal Date advancement.

This preserves a current epoch origin and relative performance clock. Simply
removing `install()` was rejected during independent review: a first `pauseAt`
initializes at zero and advances performance ticks to epoch milliseconds, which
can prematurely fire timers scheduled during setup and affect elapsed-clock
consumers. The accepted sequence avoids that jump without a future-time margin,
sleep, increased timeout, assertion weakening or Playwright private API in E2E.
See the [public clock API](https://playwright.dev/docs/api/class-clock).

The committed deterministic regression executes the actual pinned Playwright
server `Clock` and injected clock implementation in Node VM realms. It extracts
the checked-in browser journey's setup through the TypeScript parser and injects
0, 25 and 2100 ms of browser monotonic advance between host serialization and
pause delivery. Old setup: the zero-delay control passes and both delayed cases
fail with the exact reported exception. Corrected setup: all cases pass. A
separate legacy control retains the known failure assertion. The regression also
proves current Date/timeOrigin, bounded performance ticks, preservation of a
5000 ms timer queued before pause delivery, and a new 2000 ms timer that remains
pending at 1999 ms and fires after total 2100 ms.

These are actual clock/protocol tests, not native browser or real-API evidence.
The test already installs its clock after login; preexisting native timers and
the controller's previously captured native Date function are inherited. This
change does not claim to qualify lease-expiry clock behavior. The existing real
journey still requires the auth/context request, cleared captured credential
control, removed session panel and absence of the secret in browser persistence.

## Qualification boundary

A dedicated CI phase repeats only this non-mutating probe-secret journey five
times with `--retries=0 --workers=1`. Its fresh browser contexts reuse the same
synthetic tenant without administration writes. Direct, aggregate and repetition
reports remain separate. The new artifact is
`browser-administration-clock-repeat-${{ github.sha }}`; it includes the phase's
report/result directories when available; its upload step runs even on failure. Credential-bearing traces, videos
and automatic screenshots remain disabled by the existing administration file.

Local results and exact published-head native execution are recorded below and
in execution state. Source/unit evidence does not close hosted browser,
PostgreSQL, physical Windows/Android, screen-reader or installation gates. No
real accounts, credentials, adoption, deployment or installation were changed.

## Local checks

- Installed-Playwright regression: **4 passed**, including the legacy rejection
  control and all three delivery delays. Old setup produced **2 expected failures
  and 2 passes**, before applying the correction.
- Frontend core runner: **732 passed, zero failures/skips**. These four clock
  regressions are included, not counted as additional browser executions.
- Repository contracts: **22 passed**; the repeat-artifact contract was observed
  failing before its workflow step was added.
- Full frontend ESLint and Prettier passed. Touched Python Ruff check/format,
  `git diff --check`, and standalone affected-E2E TypeScript with `--strict`,
  ES2022, DOM/DOM.Iterable and Bundler resolution passed.
- The optional stronger standalone `--noUncheckedIndexedAccess` invocation
  exposes an unchanged visual-theme tuple inference at `theme[0]`. It is not
  represented as passing or changed by this correction; the normal web and
  branding-E2E project configurations remain unchanged.
- Playwright collection: **63 cases in ten files**, and **five executions of
  the exact probe case** selected by the repetition command. Collection is not
  execution.
- Qualified-environment aggregate: **21 checks passed, zero failed, five explicit
  environment blockers**. Python: **2165 passed, 224 skipped, three warnings**;
  frontend core: **732 passed**, API client: **one passed**. Full static analysis,
  offline/API types, OpenAPI/generated-client contracts, real HTTP SQLite smoke
  and production PWA build passed. PostgreSQL, Docker/client tooling, native
  IndexedDB benchmark and real browser E2E remain environment-blocked.

An initial generic-Python preflight lacked pytest/runtime dependencies; the
qualified existing dependency environment is used for final aggregate checks.
Fresh exact-candidate hosted direct/aggregate and the new retry-free repetition
remain required. Local native browser and PostgreSQL execution are not claimed.

## First PR41 hosted attempt

Head `537b2c689a40e2fe8de7138ad96b89e46f54847f`, tree
`27be03b34aa32e2d5f043067273113643b7f46c5`, synthetic merge
`64993f4d3abedfef0dce47aa67ff3370893bb623`:
[CI 38673600999](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38673600999)
failed its direct frontend core phase: **731 passed, one failed**, with all four
new clock regressions passing on Node 22.16.0. The failure is the existing
branding cache rollback assertion returning a profile for `NOW - 1`, not the
Playwright clock harness. The later aggregate's **732 core passes** do not erase
that first failure. Its **2375 Python passes / 14 skips** remain separate.
Direct browser and the five-run clock gate were skipped. Aggregate browser
launches were unavailable because the earlier failure skipped Chromium
installation; this is not evidence of 63 application regressions.

The original failure remains visible. A new exact changed-head hosted run,
including direct/aggregate browser and five retry-free probe repetitions, is
required after the separately documented cache correction.
