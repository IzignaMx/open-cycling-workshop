# Make unconfirmed shared branding visible and manually recoverable · 2026-11-27

## Source and scope

The reproduced local baseline is
`5acc4342e157b0fe7128cb0c0638b4bb06b897b0`, the PR128 login-observation candidate.
The final branch is based on its documentation-only successor
`5e99f172d6d6e185248b89e4adb12068d6505421`. That change does not alter the
production/test bytes exercised here; the source/build hashes remain the
qualification boundary. PR128's [stacked acceptance and retarget](2026-11-26-source-login-observation.md#pr128-stacked-evidence-and-retarget-to-main--2026-11-27)
are separate from the new predecessor's exact retargeted
[CI45918527486](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45918527486),
which is in progress at this observation, and from this branding candidate.
No merge or main acceptance is inherited.

The accepted [shared branding ADR](../02-technical-architecture/2026-10-14-shared-workshop-branding.md#authenticated-offline-display)
permits an older cache operation to be conservatively refused when newer trusted
observation time has advanced. Its finite coalescer permits at most one trailing
refresh; a null result or refused write does not create another request. These
admission rules remain unchanged. The [connected-startup correction](2026-10-15-connected-branding-refresh.md#bounded-lifecycle-correction)
does not promise starvation freedom under arbitrary concurrent work. This
increment addresses missing recovery information after a legitimate refusal.
UX-01, UX-10 and AC-UX-011 require clear state and visible recovery; ACC-002/010
apply to the keyboard action and announced status. No normative ADR is replaced.

## Reproduced mechanism and evidence boundary

The [November 26 probe](2026-11-26-inventory-workshop-scope.md#separate-branding-investigation)
retains three controlled production-runtime compositions. Initial sync and a
later real runtime operation advance trusted observation time during the first
and single trailing cache writes. Both legitimate refusals can leave an
operationally ready source with no accepted shared profile and no explanatory
message. An existing explicit refresh succeeds afterward. Its six production/
test hashes matched the inspected `5acc434` baseline; the original probe remains
historical evidence rather than a fresh browser result.

The native baseline uses the actual pinned PWA, whose build digest matches the
PR128 local production build receipt, and disposable PostgreSQL **18.4**. The
journey holds canonical logo digest operations **2 and 4**, preserving their
native digest results. Genuine **Primeros clientes** refreshes advance trusted
`control.observedAt` beyond each immutable cache-write entry before the held
work is released. No IndexedDB bytes are directly modified to manufacture the
refusal. The single case fails after **14.918684 seconds**, with one worker and
zero retries, because **Volver a consultar la marca** is absent (spec line 1242).
The independent fixture contracts pass **3/3**.

These controlled observations do not identify which event caused the historical
administration identity timeout in CI. They also do not explain the unrelated
source-completion CDP body failures. Neither history is reclassified.

## Bounded correction

If the cache refuses a write, the controller revalidates the exact source and
requires it still to have no accepted profile before publishing a volatile
`refreshSuggested` state. It keeps the refused profile undisplayed and does not
schedule another request. The generic notice says: **No se pudo confirmar la
marca compartida para esta vista. Puedes volver a consultarla.** A more specific
existing storage diagnostic is preserved; a false write is not relabeled as a
quota or I/O exception. An already accepted profile is not erased or downgraded.

The shell displays a **Recuperar marca compartida** section with a status message
and **Volver a consultar la marca** button in the main content. The button reuses
the existing runtime-owned explicit refresh and is disabled while that read is
pending. A subsequent failed manual read does not claim a verified copy exists
when none is accepted. Accepted cache or network content clears the suggestion;
normal cache-storage and unavailable-logo warnings retain their own meaning.

Currentness, expiry, ownership, scope and request fences surround asynchronous
work. Logout, scope change or other invalidation clears the state; an obsolete
completion cannot publish a recovery notice into another session. The finite
coalescer, 30-second ordinary-refresh throttle, timeout/retry policy, cached
payload admission and kernel are unchanged. No new grant, schema, background
loop, operational command or journal mutation is introduced.

Keyboard recovery returns focus to the main content when the activated recovery
button disappears and focus would otherwise remain on the document body. A user
who moved focus/pointer elsewhere or left the window retains that choice. The
existing settings action remains available. Notice visibility is not a claim
that the response was accepted or that automatic convergence is guaranteed.

## Local verification

The final preimplementation controller RED retained **seven failures and five
passing controls**, following an earlier six-failure selection. An additional
diagnostic-preservation regression failed against the initial candidate. The
final runtime suite passes **31 cases**, including **13 new cases**; the broader
branding selection passes **79 cases**, including those 31. Production-runtime
composition produced **three RED cases**, then **five GREEN cases** (three new
and two retained controls). Shell rendering produced **three failures and three
passing controls**, then **six passing cases**. These overlapping selections
are not additive unique-case totals.

A focused native candidate passed **1/1** in **5.120284 seconds**. The final
branding suite passed **21/21** in **111.304183 seconds**, with one worker,
zero retries, zero flaky cases and zero skips, retaining all 20 earlier cases
including four themes. The new journey observes the two actual digest fences,
then the manual **third GET** recovers the shared identity. It verifies unchanged
context/partition/journal, a disabled pending action, keyboard focus after the
action disappears, 320px reflow and 44px targets, and no critical/serious axe
findings on the notice. Its safe attachment records digest calls `[2, 4]`, three
reads and successful recovery; it does not expose credentials or business data.

The full frontend core passes **1,872/1,872**, including **22 new cases**.
Repository contracts pass **228/228** and the verifier returns OK. E2E branding,
web and offline TypeScript, touched ESLint, Ruff, Prettier and diff checks pass.
Independent review found no blocking findings.

The source/build-bound receipt is
`artifacts/branding-recovery-20261127/native-local-receipt.json`, SHA-256
`8f3f1baffeec815ac718bb550b9e8637873fc10a72e8da07b25ff80de36577bb`.
It records Node **22.16.0**, pnpm **11.17.0**, Python **3.13.5**, PostgreSQL
**18.4**, Playwright **1.64.0** and Chromium **156.0.8078.4**, revision **1248**.
The source and built asset hashes remain unchanged through final execution.
The owned PostgreSQL container and three synthetic asset directories were
removed and their absence confirmed. The local receipt retains `5acc434` as
its actual baseline; the later documentation-only predecessor does not rewrite
that provenance. Exact successor hosted qualification remains pending.

## Retained limits

V0.1 remains partial. Physical Windows/Android T1–T8/R01-T035, manual assistive
technology, G1–G6, actual installation restore, quote activation/capacity and
deployment remain separate gates. All inventory FR-INV-001–012 gaps remain in
their canonical plan. This synthetic verification neither inspects physical
stock nor qualifies a real workshop installation or a universal branding/CI fix.
