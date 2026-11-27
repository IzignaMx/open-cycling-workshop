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

## PR129 stacked evidence and retarget to main · 2026-11-27

[PR128's retargeted candidate merged](2026-11-26-source-login-observation.md#pr128-retargeted-acceptance-and-merge--2026-11-27)
as `ed8057b2b473911574f97050ce24ac537716118f`. This supersedes the earlier
predecessor-pending statement while preserving the actual local baseline
`5acc434`, its failure and the documentation-only predecessor `5e99f17`.
PR128 fresh-main CI45970597364 remains a separate pending receipt.

[PR129](https://github.com/IzignaMx/open-cycling-workshop/pull/129) head
`b49f10b1b21240c8682cf3a9ba7ca0f3c9ce4ea8`, stacked on
`5e99f172d6d6e185248b89e4adb12068d6505421`, passed
[CI45918812340](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45918812340)
and all five companion workflows. The tested synthetic merge is
`799acba763ce66899ef1e9d368b24b90d6704709`; it and the head share tree
`556de26d0de424b71fa7097bc0284347cb421104`.

Independent Python artifact `15163982390` review, SHA-256
`ac106a241ea7962f250b11bbbce9035ccfafe1b063e200302e8f601832b59871`,
confirms clean exact-source disjoint shards: **4,413 passes / 11 intentional
skips** and **2,401 passes / 47 intentional skips**, totaling **6,814 / 58**.
There are no failed, error, unrun or unexpected-skipped outcomes. Primary and
independent cleanup receipts verify owned databases absent for both shards.
Reviewed logs report **1,872 frontend passes** and **1 API-client pass**.

Independent full-ZIP/report review covered direct artifact `15164289405`,
SHA-256 `24e7e1433f0aab423b55b2934b67b7511152ec7cbd720cc27b9ebabf9b36ce6c`,
and aggregate artifact `15165635222`, SHA-256
`c661a1491f655210b3ce6059a6a1e1f0adea8b3ff4ffff0d5e0784e74de3b80a`.
Each contains **147/147 passes**, with retry zero and no errors, flakes or
skips, including branding **21**, inventory **17**, administration **16** and
source-completion **one**. Both new safe branding receipts record
`fencedDigestCalls: [2, 4]`, `reads: 3` and `recovered: true`. The source-login
observations retain zero navigation, empty session checked, response seen,
body validation, issued/stored equality and completed login, with no service
worker response. Downstream receipts preserve the source journal and confirm
two server orders. These are actual scoped synthetic journeys, not a diagnosis
of historical CI failures or physical-workshop acceptance.

PR129 is retargeted to main `ed8057b`. The clean local merge-tree check for that
base and the unchanged `b49f10b` head retains tree
`556de26d0de424b71fa7097bc0284347cb421104`. This establishes source compatibility,
not a fresh CI execution. This documentation reconciliation creates a later
retargeted candidate that still requires its own exact hosted checks and review
before merge. Branding remains the current checkpoint. The receipt supersedes
only the tested stacked source's hosted-pending statement and PR128's earlier
unmerged status; physical, inventory-completion, installation, recovery and
deployment gates remain open.
