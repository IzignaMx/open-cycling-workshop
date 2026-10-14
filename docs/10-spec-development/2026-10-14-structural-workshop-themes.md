# Structural workshop themes · 2026-10-14

Status: `implemented_pending_evidence`.
Branch: `feat/structural-workshop-themes`.
Original base: `98394826884020d9de2498cab551120087dd5334`.
Reconciled main: `c1e2230cdc18dfbb778254d9f28b0261ef32ca48`, containing
merged sync-test/runtime PRs #24/#25 and authorization PR #26, including its
test-only ambient secret-file isolation guards. Administration PR #27 is not
included in this branch; subsequent integration must preserve its migration reservations.

## Scope

All four approved compositions are implemented incrementally in Personalización:
Banco de trabajo (default), Plano técnico, Ritmo modular and Turno nocturno.
The catalog has twelve curated palettes with measured light/dark variants.
Selection affects one stable shell around the same working customer/order forms,
order operations, sync state and Conflict Center. No mock business statistics or
nonfunctional module links are introduced.

[Architecture and persistence boundary](../02-technical-architecture/2026-10-14-structural-workshop-themes.md)
contains the justified adaptations from the visual reference boards.

## Acceptance traceability

| Acceptance                                          | Implementation/evidence                                                                                                   |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Four structural directions, Banco fallback          | Theme catalog, stable shell, geometry tests with the same palette                                                         |
| Operations and permissions shared                   | One OrderList/OrderRecord and intake component; orders.write gates transitions; explicit entity reads gate cached display |
| Theme changes preserve drafts/context               | No theme keys; browser cases retain input nodes, values, selection range, search, history and radio focus                 |
| Local preferences isolated by user and organization | Validated appearance key; eleven focused pure tests include scope and storage failure                                     |
| Local logo isolated by workshop as well             | Separate record kind/key, explicit personal-local wording, offline browser reload case                                    |
| No invented shared branding                         | No new API/sync entity; shared BrandProfile and server permissions explicitly pending                                     |
| Offline-first additive persistence                  | Dexie v4 only adds preferences; browser fixture upgrades exact physical v3 and compares operational stores/queue          |
| Safe raster input                                   | MIME/signature/dimensions before decode, bounded re-encoding, CRC-validated saved PNG, preview and fallback               |
| Semantic colors and contrast                        | Protected pairs; tests cover 4×12×3 theme/palette/scheme selections; no full WCAG claim                                   |
| Touch/keyboard and reflow                           | Four desktop + four touch browser cases, 320/390/834/1440 widths, forced colors/reduced motion                            |
| Honest evidence                                     | Local browser blocked by managed URL policy; hosted tests and image review pending                                        |

## Verification log

- TDD feature red: missing personalization module before implementation.
- Adversarial red: two failing tests for unsafe object coercion and corrupt PNG
  body; both repaired and green afterward.
- Focused model/repository/logo/contrast suite: 11 passed; session lifetime guard: 5 passed; read-display gate: 4 passed (red missing module → green); conflict provenance/store→display policy: 4 additional tests passed.
- Full frontend core suite on the reconciled base plus read-display gates/provenance: 98 passed. Real/offline typechecks, repository-wide
  ESLint and Prettier, and production PWA build pass. Final aggregate qualification after review fixes: 21 passing checks, zero
  failures, five environment blockers; 577 Python tests passed, 9 live PostgreSQL
  tests skipped. Remaining blockers are PostgreSQL integration, Docker/psql
  availability, managed-policy browser navigation and the browser E2E database. No frozen-install claim: offline package metadata was unavailable,
  and preinstalled cached dependencies were reused without changing the lockfile.
  Combined proof ran at source head `b98abd69afb279e49414178122b0c03648174b4a`;
  the subsequent reconciliation commit only records this evidence and pending dependency.
- Browser suite collection on the reconciled base: 22 cases, including twelve new structural-theme/access cases.
  Collection is not execution. Each desktop/touch case attaches a screenshot;
  touch cases also attach a 320px screenshot.
- Independent review: reported boundary/focus/evidence findings fixed and re-reviewed;
  16 focused tests and real/offline typechecks independently passed. No additional
  code defects found. Full component/session-race execution is not inferred from
  guard unit tests. Exact-head hosted CI and actual-image review remain pending.
  Focused follow-up review found inherited conflict labels hardcoded to customer.
  The actual store→display regression reproduced unauthorized visibility, then
  passed after typed queued provenance and legacy fail-closed handling. Focused
  re-review cleared the correction with 22 independent auth/sync/coordinator/retry
  tests plus real/offline typechecks; real IndexedDB transaction/browser proof
  remains hosted.
  No merge or deployment.
- Added browser regressions switch a synthetic reader to a restricted user in the
  same organization/location, assert no cached customer/order/conflict content
  across all themes, and compare all operational stores/queue unchanged. A
  partial-read case hides bicycle metadata while preserving its association
  through a legal queued order transition. The exact v3 migration fixture retains
  its unverified legacy conflict unchanged; such details are hidden. Store tests
  exercise production recordConflicts code with fake tables, not real IndexedDB.
  Browser cases are collected, not run locally.

## First hosted browser evidence and correction

PR #28 head `f943f8bd982f69ec95ee5a48bd3c1bdc1b127d92`, tested merge
`af5f3864480958aa11c44c06fc78693bb8bb1e8c`, CI run `38551340262`:
17/22 browser scenarios passed in both runs; five failed. The four desktop
migration/draft/focus/axe cases, logo case, read-only/configuration case,
partial-read transition and ten pre-existing journeys passed. The four touch
cases failed at their final forced-colors assertion: imperative focus after touch
did not activate keyboard `:focus-visible`. The same-workshop restricted-user case
failed before exercising the switch because its exact label selector did not
resolve the existing customer combobox. This is partial evidence, not passing CI.

Corrections use real Tab navigation and require focused `:focus-visible` plus the
solid 3px forced-colors outline; the combobox uses its actual accessible role/name,
including the negative permission assertions. No timeout or axe threshold changed.
Downloaded artifact `11887002703` matched SHA-256
`7c0750405dc2c06d05d5da3bbcbb065634533f1829f5d778cdfd47ceab18964f`.
Independent review of all twelve original viewport images confirmed the four
structures and found 320px midword navigation wraps and a compressed monogram.
The correction uses two narrow navigation columns in unchanged DOM order and
nonshrinking logo/monogram geometry; new tests require one-line nav labels and a
square monogram. Corrected screenshots and the remaining permission scenario
require fresh hosted proof. Next artifacts include full-page desktop/tablet/320px
views, untouched Banco, canonical palettes, personal/local settings and keyboard
forced colors. Original viewport images did not prove below-fold visual quality.

Runtime run `38551340068` and Security/DCO completed successfully for this first
head. Runtime proof includes the real local stack and all three ARM64 image builds;
it does not qualify physical ARM hardware or make the failed browser suite green.

## Remaining work

Shared organization/workshop branding, server persistence, permissioned editing
and synchronization are not completed. Preserve their place in the MVP backlog.
Display gates do not erase cached data or secure it against a device owner.
Offline permission freshness, cache revocation, authorization epochs, safe
resnapshot/reconciliation and legacy conflict provenance recovery remain administration-rollout work.
Follow the existing physical-device and manual accessibility protocol, including
sunlight/reflections for the dark appearance, screen reader and 200% zoom.
