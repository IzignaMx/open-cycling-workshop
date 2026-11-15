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

## Second hosted attempt: offline navigation and pinned engine correction

CI 43685591892 attempt 1 resolved tracing startup but failed both restart cases
at the post-navigation `navigator.onLine === false` assertion. Verified artifact
14150183753 has SHA-256
`112788e011aca80c31e351312c7e313a208aa3fc9a6ef05bd86b972d6e8b1edc`.
Both phase-two traces show `false` on the blank page, successful App navigation,
then `true`; diagnostics identify Chromium 151.0.7922.34. SW navigation, index
hash and the post-cleanup legacy notice passed, but the network probe and final
snapshot were not reached. The two reload controls passed; downstream direct
browser/completeness stages did not qualify this head. This is not a completed
restart proof or a demonstrated product defect.

The failure matches the upstream Chromium emulation regression documented in
[Playwright issue 42174](https://github.com/microsoft/playwright/issues/42174) and
[PR 42925](https://github.com/microsoft/playwright/pull/42925/files): its
cross-navigation offline test requires Chromium 155 or newer. The toolchain is
therefore pinned to Playwright 1.64.0 and its official Chromium 156.0.8078.4,
revision 1248. Package metadata is checked locally; hosted native execution must
still establish whether this correction resolves our exact persistent-profile
case. No claim is inferred from an upstream test alone.

A separate native emulation control starts offline before creating its page,
checks the blank page, then navigates synthetic documents on localhost and
127.0.0.1. It checks the first document script and later evaluation, and requires
an unhandled uncached probe to fail. Only document responses are fulfilled; this
is an engine diagnostic, not App/SW/network-isolation evidence. Both existing
restart assertions and probes remain unchanged. No navigator getter override,
post-navigation offline toggle, weakened assertion, timer or retry is introduced.
The suite now collects five cases: two reload, two restart, one engine control.

The dependency delta is confined to Playwright/test/core, the existing axe adapter's
Playwright peer resolution and removal of Playwright's obsolete optional fsevents
2.3.2. Product/build dependencies retain their versions. Hosted tool-version
assertions change with the pin. Historical source pins and frozen lock hashes
remain unchanged: differing dependency locks require a separate exact frozen
installation inside the owned archive, with tracked source and installed-lock
checks. The current control derives its lock hash from committed source. Neither
path permits a new dependency allowlist or shares a different lock silently.

Native execution of the revised five-case suite remains pending. No local launch
bypasses the reported environment restriction. G1–G6 remain open; no activation,
selector, schema, runtime policy or deployment is included.

Corrected-engine local checks: **1,577 frontend passed**, **209 repository
passed**, **25 process/configuration controls passed**, and **30 PWA fixture
controls passed**. Types, lint, formatting and two production-isolation checks
pass. Both historical archives reproduce seven assets with isolated exact-lock
installs; current committed archive build is verified when sealing the candidate.
Five browser cases are collected, **zero executed locally**. Prior failed hosted
runs are preserved, not relabeled as passes.

## Third hosted attempt: stale mock tool-version fixture

CI 43689744807 stopped its direct Python run at 2,193 passes, five skips and one
failure: the quote-ownership database mock still returned `Version 1.62.0`, while
the reviewed tool preflight required 1.64.0. The preflight correctly refused the
mismatch before connecting. This fixture oversight does not invalidate that
fail-closed behavior; reported cleanup remained `verified_absent`. The failed
attempt is not relabeled as successful and its native stages require separate
inspection.

The mock now returns the explicit 1.64.0 literal, independently of the expected
constant. Additional controls reject 1.62.0, 1.64.1 and malformed versions before
any connection or query. Existing identity/role rejection tests remain. Searching
active tests, scripts, workflows and package declarations found no other stale
positive 1.62.0 fixture; historical documentation assertions are retained. The
full affected file reproduced 20 failures before correction and now passes all
41 tests. New source-bound CI is pending; no blind retry, runtime change,
selector activation or deployment is included.
Affected operations suite: **1,699 passed, three PostgreSQL-environment skips**;
repository checks: **209 passed**. These scoped local results do not substitute
for the pending full hosted Python, aggregate or native qualification.

## Explicitly authorized shared-button contrast correction

The same third hosted attempt also reported 139 direct browser passes and one
unexpected accessibility failure (reproduced on retry) in the mounted-theme
administration case. This is distinct from the historical identity-readiness
flake. Axe reported serious text contrast: foreground `#5e665b` on background
`#82b095`, approximately 2.436:1, below the unchanged 4.5:1 requirement.

Source inspection identifies the shared Button's generic Tailwind `transition`:
compiled CSS includes both color and background-color. Light-to-dark Bosque
endpoints pass (white on `#285b46`: 7.85:1; `#172314` on `#a9d5b7`: 10.01:1),
but their intermediate colors can fail. The reported pair is consistent with
this interpolation. The evidence does not establish that Chromium introduced a
new product defect or explain every timing difference from the previous engine.
Axe's package version and required threshold are unchanged.

The owner explicitly authorized this small product correction in PR108: replace
generic Button transitions with shadow-only transitions, preserving palette,
hover colors, focus tokens, disabled state and click/submit behavior. Two tests
execute the actual transpiled component; the transition test failed before the
change and both pass afterward. The mounted-theme E2E also requires a nonempty
set of shared buttons whose computed transition property is only `box-shadow`.
Existing axe assertions remain intact, with no timer, reduced-motion override,
rule exclusion or relaxed threshold. Native validation of this correction is
pending on the newly published source, not inherited from prior attempts.

This explicitly expands the earlier test-only scope by one Button class change.
It changes presentation only, not capture format, selector, authority, data,
recovery semantics or deployment. G1–G6 remain open.

Local contrast-candidate checks: **1,579 frontend passed**, **209 repository
passed**, including the two new Button controls. App and branding types, lint,
formatting and administration collection (16 cases) pass. An additional isolated
whole-administration typecheck finds one pre-existing TS2769 at the indexed theme
expectation: the identical diagnostic reproduces against committed pre-fix source
(line 1013, now 1027). That extra check is not reported as passing or repaired by
this change. No native browser was launched locally; full hosted acceptance is
pending for the corrected source.
