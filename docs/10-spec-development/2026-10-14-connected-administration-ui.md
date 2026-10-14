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
