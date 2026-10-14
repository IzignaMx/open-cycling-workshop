# Connected administration UI: scope and evidence

Status: implemented_pending_evidence. Date: 2026-10-14.
Base: main38 `79cb4055aeb34344f2182d77e244c8187e9bb71b`;
base tree `9a26bebbd05f54508b3432b28759a44878d17d2e`.

The [architecture record](../02-technical-architecture/2026-10-14-connected-administration-ui.md)
defines the finite account/workshop UI boundary. This is source implementation,
not installation or full MVP/release certification.

## Inherited exact baseline evidence

Main38 postmerge evidence was independently reported for the exact base above:
[CI 38630382271](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382271)
passed all 27 qualification checks, 1825 Python tests with 12 explicit skips,
578 frontend tests, 11 native IndexedDB and 27 production browser cases; repeated
20+9 cases were retry-free.
[Runtime 38630382283](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382283)
passed all eleven checks, restore and three ARM64 cross-builds.
[Security 38630382252](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382252)
scanned 211 content commits and 40 active packages with zero findings.
This inherited evidence does not qualify the administration changes.

## Observed development evidence

- Independent plan review required account-only admission without operational
  baseline and a separately fenced post-cancel self-command handle.
- RED was observed for absent runtime account facade, absent model/transport/UI
  modules, invalid bodyless no-store, offline during authority-lock wait, owner
  lookup duplicate dispatch, inconsistent actor-row authority, and derived
  capture handles rejected by the runtime's exact-handle boundary.
- GREEN covers the corrected focused runtime/transport/model/state regressions.
  Source-contract panel checks establish source structure only, not mounted DOM
  behavior. Emulator tests remain distinct from native IndexedDB evidence.
- Integration review corrected username bounds, editor version/draft rebasing,
  filter/cursor mismatch, guarded local logout, exact current401/403 invalidation
  and owner lookup consistency before exhaustion.
- The existing core runner registers administration and runtime tests; exact
  final counts and static/build commands are recorded in execution state after
  final-tree execution. No blocked test is represented as passing.

## Executed final local checks

- `node apps/web/tools/run-core-tests.mjs`: 645 passed, zero skipped.
- `pytest -q` with the qualified Python3.13 dependency environment: 1643 passed,
  194 explicit skips and one warning. PostgreSQL was not configured; these skips
  remain visible and do not qualify locks, migrations or real concurrency.
- Web and offline TypeScript, API-client TypeScript and its one core test passed.
- Full ESLint, Prettier, Ruff check/format and mypy passed; generated OpenAPI,
  generated TypeScript and repository contracts passed unchanged.
- Production Vite/PWA build passed with service-worker generation and five
  precache entries. The existing large-chunk warning remains nonblocking.
- Focused runtime: 115 passed. Feature model/transport/state: 40 passed.
  Six panel source-contract checks passed. These are included in the aggregate,
  not additional independent browser proof.
- `playwright test administration.spec.ts --list`: 16 collected, not executed.
  Fixture syntax/style, distinct-ID checks and mocked activation/readback
  choreography passed; 32 dedicated initial/retry tenants are not locally seeded.

An initial aggregate preflight reported unavailable tools because its generic
PATH lacked the qualified environment; subsequent explicit commands above ran
those tools. Native Chromium remains policy-blocked, PostgreSQL unconfigured and
Docker qualification unexecuted locally. No restriction was bypassed.

## Hosted acceptance work

The production Playwright suite includes dedicated administration journeys using
real FastAPI endpoints and isolated synthetic PostgreSQL tenants, independent of
shared Golden Slice fixtures. Each stateful case and CI retry has a distinct
tenant. Seed tooling retains loopback and `_test`/`_e2e` guards and explicitly
activates/readbacks genuine floor1 for each administration tenant. Mock seed
choreography and collection are not PostgreSQL execution evidence.

Journeys cover users and individual grant replacement, account/selected/directory
scope, zero locations, no-sync/empty-grant self controls, location creation without
selection, self logout/password reauthentication, version/owner refusals and a
real server commit followed by deliberately lost response. Deterministic browser
interceptions are identified separately from server authorization claims.
Four-theme native journeys exercise drafts, focus, axe, narrow/tablet/desktop,
forced colors, zoom and expanded text, and emit screenshots for actual review.
Credential-bearing cases disable traces/video/automatic failure screenshots;
explicit captures occur with credential inputs empty.

Local Chromium navigation is blocked by managed policy. No policy bypass or
alternative local native execution is attempted. Collected cases and passing
TypeScript do not prove browser behavior, screenshot readability, service-worker
cutover, PostgreSQL concurrency or restore. Exact published-tree CI must run
existing and new direct/repeated/aggregate journeys and the unchanged disposable
11-check Docker runtime/restore qualification. Review actual screenshots before
claiming visual readiness. Existing physical Windows/Android, manual screen-reader
and actual installation recovery gates remain open.

No backend API, schema, dependencies, production accounts or persistent access
were changed. Source qualification does not authorize a deployment or actual
installation update.

## First hosted browser result and bounded corrections

PR39 first published head `8ad167d93947265925674ff61a0fd6bfbb07c832`
has the same tree as local `c2fe0467ee953b52e17ffd5aee9385ea030b481d`:
`36a8219a52a5c05018fda72b640481ffd4ec209e`. CI
[38634454187](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38634454187)
tested merge `226e858da7722b2bf7bdeae635e587c60e8b130b`. Its direct-browser
artifact 11929181304 (SHA256
`d9a2bfcece9f024834d5e7c10fe4572e21569ac44c1ec826f5062f6b7dba876e`)
reports **30 passed, 13 failed, zero flaky/skipped**. Retries did not clear the
failures. This is actual failed native evidence, not a timing-only assumption.

- Ten administration failures cluster around catalog/directory reads and direct
  commands that never reach their expected server/interception boundary. Native
  fetch was invoked as a property of an options object, assigning the wrong
  receiver. A strict-receiver transport regression failed before dispatch, then
  passed when explicitly invoking with the global receiver. URL/currentness,
  response/refusal validation and command non-retry behavior are unchanged.
  Administration traces remain intentionally disabled for credential safety;
  the artifact does not directly record `Illegal invocation`. A new genuine
  native run is required to establish the complete causal closure.
- Two prior preservation/isolation cases encountered logout confirmation and then
  the original session resumed during attempted login. One was a false prompt:
  the input-history latch stayed true after a customer had been saved and all
  fields cleared. Current model-owned form markers now distinguish unsent values
  from historical edits. Successful order save preserves customer/priority as
  clean defaults; failed or pending saves and real drafts remain guarded.
  Search and presentation input are not operational drafts. Selector workshop
  choices now use the same discard guard as operational workshop transitions.
- The restricted-user case deliberately leaves two private unsent drafts. Its
  confirmation is legitimate. The corrected journey first dismisses the exact
  prompt and proves draft/principal/partition/journal preservation, then accepts
  the prompt before continuing all existing cross-user isolation assertions.
- All four unzoomed 320px theme captures reached their assertions, but a later
  CSS 200% check retained a 320px viewport, demanding 160 CSS px while the established
  layout minimum is 320 CSS px. The separate zoom check now measures a 640px viewport
  and CSS factor 2, explicitly asserting 320 effective CSS pixels and no overflow.
  True 320px unzoomed checks remain; expanded-text checking restores 320px at 1x.
  This is not a claim of 160 CSS px support or physical browser zoom qualification.

Observed local correction evidence: receiver RED→GREEN, dirty-state composition
RED→GREEN, **650 core tests passed**, real/offline TypeScript and source lint.
All **43 browser cases across 9 files** remain registered. No timeout, server
permission, storage fence, original preservation assertion or credential-artifact
safety control was relaxed. Final exact-source native execution and screenshot
inspection remain pending; local checks do not close the failed browser gate.

## Second hosted browser result and exact role locator correction

Correction head `07617df9d91c8f2ef5d10972688d313817f00acb` (tree
`6a4c7c002064e77871bf93f3b6f6c18f58c4519a`) ran in CI
[38639134363](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38639134363),
merge `d9cd401a0c23451fa08de3123d9a1036ec0f49ab`. Direct artifact 11929384786,
SHA256 `1cc9fae4023828cfe8ace3de73af184c9cdebc380cab4037b454d298f41e3332`,
reports **41 passed, two failed, zero flaky/skipped**. Original preservation and
restricted-user isolation cases passed, as did actual administration transport,
self-session/lifecycle and measured reflow journeys. This does not qualify the
whole administration slice: user creation/grant replacement and the multi-theme
visual-state journey still failed on initial attempt and retry.

Both remaining waits target `getByLabel('Rol', { exact: true })`, although their
accessible snapshots expose an enabled `combobox` named `Rol` with expected
options. Inspection and an isolated execution of installed Playwright 1.62's
`getElementLabels`/`elementText` confirm that matching the wrapping label includes
nested option text. The fixture now uses a form-scoped exact accessible combobox
name for all three role selections, including the later grant replacement.
Selected role values, response checks, security review and actor-isolation
assertions remain unchanged. This locator correction does not change production
UI or permissions.
A deterministic fixture-contract regression was observed RED then GREEN; this
source check does not substitute for a new native run. All 43 cases remain;
complete four-theme visual-state captures and final hosted closure are pending.

### Observed enlarged-layout readability correction

Actual full-resolution capture `administration-forced-colors-200-percent.png`
showed four operational KPI columns squeezing words into single-letter fragments,
and a cramped identity/header, despite passing no-horizontal-overflow assertions.
A 640px viewport enlarged by CSS 200% leaves 320 CSS pixels for content while
viewport media queries still see 640px. Readability was therefore not qualified
by the earlier overflow result. Metrics now use intrinsic minimum-width auto-fit
columns; the compact header wraps its identity/settings and gives navigation an
intrinsic grid. This is available-width responsiveness, with no zoom detection,
DOM remount, theme-token change or permission/session change.

The existing four-theme journey now checks complete-word width for KPI, identity,
settings and navigation labels and one-line OCWP identity at both true 320px and
CSS 200%/effective 320px, retaining the original captures and adding one enlarged
capture per theme. It continues to assert exact geometry, no overflow and mounted
administration draft preservation. The forced-colors capture also checks these
readability conditions. Full-page captures first scroll to document origin
without blurring the focused control and assert the unfocused skip link remains
above the viewport. This avoids including the translated fixed link at a stale
scroll offset in a stitched full-page image; a genuine hidden-link geometry or
focus failure will fail the journey. No production skip-link behavior changed.

Intrinsic-layout source regressions were observed RED then GREEN. These are
source checks; the expanded native assertions and actual screenshot inspection
remain pending on the next exact published tree. CSS enlargement is not physical
browser/device zoom or manual screen-reader qualification.

Final local source checks for this bounded correction: **652 core tests passed**,
eight panel/source regressions passed, whole-repository ESLint and Prettier,
strict affected E2E compilation, production TypeScript/Vite/PWA build and repository
contract check passed. Full browser collection remains **43 cases in nine files**;
collection is not execution. Independent source review closed the measured-label
count and inherited compact flex-direction issues before handoff. No local native
browser, PostgreSQL or physical-device execution is claimed for this correction.

## Third hosted result: confirmed drafts and isolated visual scenes

Head `b9f5b435998b3c150e9a8247e4bc72b5c2bdc440`, tree
`32a7822e899515b76b23ac47cb2435efedb43605`, ran in CI
[38641877744](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38641877744)
as merge `fd7d9f75132f1d6d52b8eede270edfc2f738f50d`. Verified direct artifact
11931620940, SHA256
`a6d42ef3f7fae04fbce9516e2683457c63e883de307e3a41c94c7af6bb2a9d0a`, reports
**41 passed, two failed, zero flaky/skipped**. The exact role selection now works:
user creation returned 201 and the created identity/grants were read back. The
journey subsequently failed opening its editor because the successful create
form retained a historical dirty flag and remained mounted after the discard
click. Source behavior plus the retained-form snapshot support unattended
confirmation dismissal; credential-safe traces do not directly record that dialog.
The second failure occurred only after deliberate label expansion: a focus
assertion still selected the control by its original unexpanded accessible name.

Retained user create/edit, location-create and targeted-security forms now use a
local edit revision and a per-command `confirmed` receipt. A receipt is returned
only for a current non-self successful command, rechecked after success hooks,
status publication and busy cleanup. Refused, uncertain, unauthorized, duplicate,
stale and self-invalidating completions cannot clean a draft. A form additionally
requires its original mounted instance, current feature generation and unchanged
submitted edit revision before becoming clean. Newer input is never overwritten;
immutable reviewed user versions are not rebased. Self-password suspension owns
unmount/invalidation; submission no longer prematurely marks that form clean.
There is no new persisted receipt/session store or retained credential material.
The real create journey now explicitly asserts the successful form is clean,
closes without a dialog, and continues existing permission/actor checks. The
expanded-label focus check uses the original connected element handle.

All four enlarged-layout automated geometry checks passed in that native run.
Actual pixel review confirmed readable KPI and identity layouts, but identified
an isolated final letter in the Administración navigation item. The intrinsic
navigation minimum is now 9rem; single-word navigation labels must occupy one
native text Range line. Canvas comparisons no longer allow a one-pixel deficit
and include letter spacing. New exact-tree pixels remain required.

The visual-state journey passed assertions but its nominal twenty filenames did
**not** prove twenty independent states: later directory captures retained the
prior editor, review selection, location draft and uncertain-result banner. Two
directory/uncertain pairs were byte-identical. The fixture now explicitly accepts
the exact discard prompt for deliberately unsent/refused synthetic drafts,
closes administration and uses ordinary reload/reverification for each next
theme. No browser storage or journal is deleted. Before named captures it asserts
clean directory state or the specific editor, role, review, error and location
draft state. Credential-empty screenshots are full-page captures from document
origin, avoiding the element-scroll fixed skip-link overlay seen in those images.
The prior twenty captures are retained as diagnostic evidence, not accepted as
complete state coverage. Expanded-label capture and the corrected scene matrix
remain pending on the next native run and actual pixel review.

Local verification for this correction: **661 core tests passed, zero skipped**;
focused draft/panel checks passed 12 tests and controller checks passed 21.
Whole-repository ESLint/Prettier, real/offline TypeScript, strict affected E2E
compilation, production Vite/PWA build and repository contract passed. The full
browser suite still collects **43 cases across nine files**. Receipt refusal,
uncertainty, stale completion, single-flight rejection and synchronous
publication/cleanup invalidation are tested independently of source-only form
composition checks. None of those checks is a new native browser result.

## Fourth hosted result: visible theme verification order

Head `9165077a316938702d5d1780fe7485c74085231c`, tree
`7be60b48e3a507e25f447b938b086c7b3ddffcaf`, ran in CI
[38644565981](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38644565981)
as merge `0d982ba47ccf5e2bda01ba17573283883e79436f`. Verified direct artifact
11932970558, SHA256
`280efae2dd204ecfad53693fa42a3803f2e16138cafcb997ded4cb5ce7755627`, reports
**42 passed, one failed, zero flaky/skipped**. The user create/grant replacement
journey and full four-theme reflow/expanded-label focus journey now pass. The
isolated visual-state journey stops before its first capture: it checks the
selected radio after Escape has hidden its personalization panel, so the default
accessible-role locator correctly cannot find it. Initial and retry fail alike.

The fixture now verifies the selected radio immediately after Space while it is
visible, then preserves Escape, focus-return and exact shell-theme assertions.
No hidden-element workaround, timeout increase or assertion removal is used.
Remaining same-scene locators were audited: later editor absence checks occur
after explicit discard; controls used for interaction/state checks are mounted,
and the next scene reloads and reverifies before selecting a theme. Production
source is unchanged. A source ordering regression was observed RED then GREEN.
A new full native run and actual state-matrix pixel review remain required; the
missing matrix cannot be inferred from the 42 passing cases.

Local fixture-only correction checks: **662 core tests passed, zero skipped**;
nine panel/source tests, whole-repository ESLint/Prettier, strict affected E2E
compilation and repository contract passed. Full browser collection remains
**43 cases across nine files**. Production assets are unchanged; this correction
does not claim a new native run or replace the pending actual scene review.
