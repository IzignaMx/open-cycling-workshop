# Recovery and workshop-selector presentation · 2026-10-14

Status: implemented; exact integrated-head hosted visual requalification pending.
Base: `022cb0466d9b391c6e4bf93fbdf6b9c8cc6c5eb6`.

## Observed defects and scope

Actual pixel review of the PR38 direct-browser artifact `11922880494`, source
head `70f16fc1`, found two minor presentation defects:

- All eight `authenticated-recovery-{theme}-{1440,320}.png` images expose the
  internal `held_recovery` state within otherwise Spanish incident text.
- `authenticated-workshop-selector.png` and
  `authenticated-workshop-selector-320.png` show vertically touching workshop
  choices. The buttons remain readable, but their separation is unclear.

The artifact ZIP SHA-256 is
`e36d2cee7d5b4f0c4c8dbf24445e6843787550dd6ca20076a4bd433ef7159537`.
The same review found no clipping/overlap in the captured selector, held,
four-theme recovery, canonical theme or settings views. It did not establish
WCAG conformance. Two unrelated reconnect E2E failures remained open.

## Presentation contract

- Retained-work state text uses a closed Spanish map for the existing seven
  issue states. Unknown values, including inherited object-property names,
  display `Requiere atención`; never echo an unknown protocol state.
- Original state, journal, delivery, IDs, error code/message, ordering, access
  controls and recovery behavior remain unchanged. This is display-only and
  introduces no reconciliation or automatic replay action.
- The existing semantic workshop-choice list receives a 12px row gap and 12px
  block margins. Button labels, order, focus, handlers and responsive behavior
  remain unchanged. No timeout or permission changes are included.
- The existing real `/sync/baselines/start` response gate now also captures
  `authenticated-baseline-progress-320.png` before releasing the same successful
  server response. No fabricated runtime or baseline is introduced. The journey
  checks narrow overflow and axe results, then restores its desktop viewport.
- Selector geometry must show at least 12px between adjacent buttons at desktop
  and 320px. Each existing four-theme recovery capture must show the Spanish
  operation label and omit the raw state string.

## Evidence boundary

The focused state-label regression was observed RED before the display mapper
existed: two existing checks passed and the new label check failed. It then
passed with known labels and unknown/prototype-key fallbacks. The screenshot
review above is the visual RED evidence for selector spacing. Authored browser
assertions and screenshot collection are not local browser execution.

Local verification on the corrected source:

- Frontend core: **536 passed**, zero failures or skips.
- Web/offline typechecks and strict compilation of both affected E2E specs pass.
- Whole-web ESLint, touched Prettier and `git diff --check` pass.
- Playwright collection: **27 cases in eight files**, not browser execution.
- Production PWA build passes; generated assets are not committed.

Independent source-review confirmation accompanies the exact committed-tree
handoff. The existing screenshot evidence is from the prior head, not this
correction's rendered output.

Managed Chromium restrictions remain in force. Final hosted screenshots must
be inspected after integration; the new 320px progress capture does not exist
until that journey actually runs. No prior release, physical-device, browser,
PostgreSQL, restore or installation gate is advanced by this correction.
