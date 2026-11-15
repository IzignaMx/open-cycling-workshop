# Persistent-profile capture restart qualification

## Decision and baseline

Baseline main `15d6dd23135b6571f1770e70279fb9abb673a3f3` has the exact PR107
tree `92cb7c37ab649870e8d1623461773b648a22b57a`. Hosted
[CI 43586596616 attempt 1](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/43586596616)
passed its two actual App/SW page-reload cases and three reducer/storage cases,
all without retry. Those results qualify that baseline, not this increment.
The dated earlier local pending entries remain historical receipts.

The next bounded gap is **graceful browser-process restart** with persisted SW,
cache and IndexedDB in the same disposable profile. Reload inside a live browser
does not establish that boundary. This integrity prerequisite advances G2 without
activating richer capture data or choosing a deployment architecture. Master Loop,
OFF-007 and operational upgrade/recovery rules remain unchanged. V0.1 physical
acceptance is still separate.

## Test design

Retain both existing page-reload scenarios. Add two independently owned profile
cases, one for the exact historical cc18a203 App/SW and one for current HEAD.
Both use the existing archived-source, frozen-lock and served-byte provenance.
Only synthetic data and temporary profiles are used; no account or backend exists.

1. Create a fresh owned temporary profile. Launch Chromium with a persistent
   context and identify its browser process through public CDP SystemInfo data.
   Linux `/proc` PID/starttime plus profile ownership evidence bind the process.
2. Establish the existing inert-page legacy sentinel and actual App's post-cleanup
   notice before seeding the future-format order, exact-v1 customer, expired
   maintenance witness and intact journal control. Record the committed snapshot.
3. Close the browser context and require complete termination of that process.
   Disconnection or a second PID alone is insufficient. Only verified process
   absence permits the next launch; permission, parse and timeout errors fail.
4. Launch a new browser process with the same profile and `offline: true` from
   creation. Require a distinct process identity and initially inert pages.
   No reseeding, profile copying, storageState import or TTL refresh is permitted.
5. Navigate to the same origin. Require the response from the installed SW and
   exact index hash, the actual App's completion notice, offline state and a
   failed uncached request. Compare persisted content/checkpoint/journal with the
   original pre-close snapshot, and require maintenance witness removal.
6. The historical control must reproduce future-row deletion and UNAVAILABLE;
   the current control must preserve future bytes and checkpoint. Both preserve
   exact-v1 content and journal. Retain process evidence and separate traces for
   both launches. Remove only the owned synthetic profile after its processes
   have demonstrably closed; uncertain cleanup fails visibly.

## Scope boundaries

This is Linux Chromium and orderly shutdown, **not crash consistency**, power
loss, abrupt termination or supported-platform acceptance. Playwright offline
contexts plus failed network probes are not an OS-wide air gap. Separate old and
current profiles are independent controls, not update, rollback, migration or
handover. Successful historical deletion remains a counterexample to shared-origin
new-format activation, never proof that old clients were excluded.

G1–G6 remain open. No production writer, format, schema, runtime, security setting,
SW policy, selector, credential flow or deployment changes. Shared-origin writes
remain exact v1. A new origin is still a proposal requiring an accepted transition
ADR and complete handover/rollback/privacy evidence.

## Candidate evidence

Native execution is pending. No local launch is attempted to bypass the previously
reported environment restriction. Four cases being collected means two existing
reload cases plus two authored restart cases, not four native passes. Hosted CI
requires separate publication authority. A successful future run contributes only
the stated graceful-restart evidence to G2; it does not close that gate.

Tests-first controls cover process evidence, failure ordering and ownership rather
than accepting a disconnect-only claim. Frozen local checks: **1,573 frontend
passed**, **209 repository passed**, **23 behavioral process controls passed**;
TypeScript, ESLint, formatting, Ruff, repository contract, PWA build and two
production-isolation checks pass. Both archived App distributions reproduce seven
assets. Four browser cases are collected, **zero executed locally**. The original
two reload cases remain byte-identical to baseline main.

Independent source review accepted the final lifecycle, profile ownership and
claim boundaries without blocking findings. The broad exploratory preflight
finished with 21 passing checks and five environment blockers, but began before
implementation and is not a frozen full-backend or full-aggregate qualification.
Its Python collection and later frontend run are not presented as one candidate
receipt. The blockers concern PostgreSQL/E2E URLs, Docker, PostgreSQL tooling and
the managed Chromium navigation policy; no browser restriction was bypassed.

Final source/archive identity and all receipts are retained in the durable review
backup. Earlier baseline CI is not reused as qualification of this candidate.

## PR108 first hosted attempt and tracing correction

CI 43682997245 attempt 1 failed both new restart cases at manual tracing startup:
`Tracing has been already started`. The Playwright runner also instruments manually
created persistent contexts. Failure occurred before process identification and
fixture seeding, so that attempt provides **zero restart evidence**. The two reload
controls passed. Downstream browser/completeness stages did not qualify the candidate.

The correction disables runner tracing only in the restart suite, preserving its
manual trace for each process and the global/reload tracing configuration. A
configuration regression executes the transpiled real suite declarations against
a registration recorder: missing override failed (`on` versus `off`), then both
restart declarations resolved to `off` while reload remained `on`. It also checks
the retained phase-specific manual start/stop paths. This control is not native
execution; source-bound hosted rerun is still required. No blind rerun, production
change, selector activation or deployment is part of this correction.

Corrected-source local validation: **1,574 frontend passed**, **209 repository
passed**, **24 process/configuration controls passed**; types, lint, formatting
and four-case collection pass. Zero native cases executed locally. These results
do not turn the failed hosted attempt into a pass; the corrected head needs its
own native CI evidence.
