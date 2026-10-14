# Structural workshop themes · 2026-10-14

Status: `implemented_pending_evidence`.
Branch: `feat/structural-workshop-themes`.
Base: `98394826884020d9de2498cab551120087dd5334`.

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

| Acceptance                                          | Implementation/evidence                                                                                          |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Four structural directions, Banco fallback          | Theme catalog, stable shell, geometry tests with the same palette                                                |
| Operations and permissions shared                   | One OrderList/OrderRecord and intake component; orders.write gates all transition affordances                    |
| Theme changes preserve drafts/context               | No theme keys; browser cases retain input nodes, values, selection range, search, history and radio focus        |
| Local preferences isolated by user and organization | Validated appearance key; eleven focused pure tests include scope and storage failure                            |
| Local logo isolated by workshop as well             | Separate record kind/key, explicit personal-local wording, offline browser reload case                           |
| No invented shared branding                         | No new API/sync entity; shared BrandProfile and server permissions explicitly pending                            |
| Offline-first additive persistence                  | Dexie v4 only adds preferences; browser fixture upgrades exact physical v3 and compares operational stores/queue |
| Safe raster input                                   | MIME/signature/dimensions before decode, bounded re-encoding, CRC-validated saved PNG, preview and fallback      |
| Semantic colors and contrast                        | Protected pairs; tests cover 4×12×3 theme/palette/scheme selections; no full WCAG claim                          |
| Touch/keyboard and reflow                           | Four desktop + four touch browser cases, 320/390/834/1440 widths, forced colors/reduced motion                   |
| Honest evidence                                     | Local browser blocked by managed URL policy; hosted tests and image review pending                               |

## Verification log

- TDD feature red: missing personalization module before implementation.
- Adversarial red: two failing tests for unsafe object coercion and corrupt PNG
  body; both repaired and green afterward.
- Focused model/repository/logo/contrast suite: 11 passed; session lifetime guard: 5 passed.
- Full frontend core suite: 88 passed. Real/offline typechecks, repository-wide
  ESLint and Prettier, and production PWA build pass. Final aggregate qualification after review fixes: 21 passing checks, zero
  failures, five environment blockers; 476 Python tests passed, 8 PostgreSQL
  tests skipped. Remaining blockers are PostgreSQL integration, Docker/psql
  availability, managed-policy browser navigation and the browser E2E database. No frozen-install claim: offline package metadata was unavailable,
  and preinstalled cached dependencies were reused without changing the lockfile.
- Browser suite collection: 19 cases, including ten new structural-theme cases.
  Collection is not execution. Each desktop/touch case attaches a screenshot;
  touch cases also attach a 320px screenshot.
- Independent review: reported boundary/focus/evidence findings fixed and re-reviewed;
  16 focused tests and real/offline typechecks independently passed. No additional
  code defects found. Full component/session-race execution is not inferred from
  guard unit tests. Exact-head hosted CI and actual-image review remain pending.
  No merge or deployment.

## Remaining work

Shared organization/workshop branding, server persistence, permissioned editing
and synchronization are not completed. Preserve their place in the MVP backlog.
Follow the existing physical-device and manual accessibility protocol, including
sunlight/reflections for the dark appearance, screen reader and 200% zoom.
