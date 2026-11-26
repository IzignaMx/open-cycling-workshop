# Retry a failed inventory page explicitly · 2026-11-26

## Scope and baseline

Baseline: merged main `c65d54d6adc5e262356a883ef378a0696e7cb363` (PR125).
The [prior candidate/merge receipt](2026-11-26-inventory-accessible-actions.md#pr125-candidate-acceptance-and-merge--2026-11-26)
qualifies the accessible catalog actions within its scoped evidence and preserves
the separate administration identity-readiness flaky case. Its pending main run
is distinct from this inventory-page recovery increment.

The accepted [connected inventory read ADR](../02-technical-architecture/2026-10-15-connected-inventory-read.md)
requires explicit reads, bounded volatile pages, current authority and no automatic
retry. Failed reads clear displayed data; scope/session/offline invalidation clears
volatile state. Newest/refresh resets the traversal boundary. This increment adds
manual recovery of the current failed page within those existing rules; no ADR,
API, schema, ledger, inventory command or offline-stock behavior changes.

[Phase 1](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md)
NFR-010 (graceful degradation), ACC-002 (keyboard operation) and ACC-010 (announced
sync/error states), together with the ADR's explicit error/recovery UX, apply.
FR-INV-001 and all other inventory requirements retain their prior partial/planned
scope; a read-recovery control does not complete product management or stock
reconciliation.

## Observed recovery gap and bounded behavior

The controller retains the requested catalog offset and movement-history boundary
when a page read fails, but the panel provides no direct action to retry that
failed position. Catalog refresh returns to the first page, and movement Newest
returns to the beginning of history. A transient failure while moving forward
therefore loses the user's continuation path even though its safe position is
already available in current volatile state.

The correction adds explicit error-state controls:

- **Volver a consultar esta página** retries the failed catalog offset.
- **Volver a consultar estos movimientos** retries the failed history boundary
  for the still-selected product, including the initial page's absent cursor.

Retry actions reuse the ordinary catalog/history read methods and their current
account, workshop, product, generation and request fences. They act only on the
current corresponding error state, with ready access and `inventory.read`, and
refuse `invalid_session`/`capability_denied` outcomes. They do not reverify access
or create a background loop. Loading,
ready or cleared state is not a retry request. Scope/account changes, offline,
expiry, refusal and unmount continue to invalidate the old work; late responses
cannot republish it. Independent stock/history receipt freshness remains separate.

The existing **Actualizar catálogo** and **Movimientos más recientes** controls
retain their reset behavior. A retry preserves query position, not a server-side
snapshot or exact historical result: the ADR still defines live pagination.
No cached stock, successful failed-request receipt, cursor authority, automatic
network request or extra persistence is introduced. Keyboard activation returns
focus through the existing catalog/history heading path, and existing error/status
announcements remain available.

## Verification boundary

Initial controller/panel regressions produced **eight expected failures and 14
passing controls**, then **22 passing cases** after the retry implementation.
Strengthened authority guards subsequently produced **three expected failures
and 22 passing controls** before the final guard correction, then the final
focused suite passed **25/25** (19 controller and six panel cases, zero failures
or skips). Inventory compilation, E2E typecheck and touched ESLint/Prettier/diff
checks passed; independent source review found no blocking findings. Full core
passed **1,817/1,817**, with zero failures/skips (34.14-second test phase).
Repository contracts passed **227 tests** (3.48 seconds) and the verifier passed.
These tests exercise exact offset and
initial/older-history cursor reuse, no automatic/duplicate dispatch, unchanged
stock receipt, Newest reset, scope changes and current versus stale refusals.

The native baseline produced **one failed case with zero retries** against the
frozen `c65d54d` PWA: after one synthetic HTTP503 at catalog offset 50, the explicit
page-retry button was missing. The baseline error report and accessibility context
are retained. The same updated journey is used against the rebuilt candidate,
with bounded one-time HTTP503 failures for catalog and history pages. It also
checks 320px error-state reflow, 44px control targets, keyboard/heading focus,
request-position equality as a boolean and preservation of the stock receipt.
The candidate PWA build passed with Node **22.16.0** and pnpm **11.17.0**.

The native candidate passed **17/17 cases** in **50.2 seconds**, with one worker,
zero retries, zero flaky cases and zero skips. After the synthetic catalog failure,
Enter retries the same offset-50 request and receives the actual server's second
page. After the older-history failure, Space retries the same cursor request and
receives its four rows. URL/position equality is asserted as booleans; the stock
receipt stays unchanged. The error-state 320px target/reflow and keyboard/focus
checks pass, alongside existing four-theme axe, touch, reflow and safety cases.

Source/build-bound local evidence is retained at:

- `artifacts/inventory-retry-20261126/baseline-build.json`
- `artifacts/inventory-retry-20261126/native-local-receipt.json`
- `apps/web/test-results/inventory-retry-red-20261126-report.json`
- `apps/web/test-results/inventory-retry-green-20261126-report.json`

The receipt's SHA-256 is
`3802c93237c938ce7615a4016be10c6145cb38b94c0ada5caac3fe45c5b99d7a`.
Its source and built-asset hashes were checked unchanged through the candidate run. The owned PostgreSQL container was removed and its absence
confirmed. Final E2E type/lint checks passed. Results above are overlapping
invocations, not additive unique-case totals. Exact successor hosted qualification
remains pending; prior source receipts do not qualify this candidate.

## Product and operational limits

V0.1 remains **partial**. The [inventory audit](2026-11-25-project-inventory-audit.md#inventory-requirements-retained)
retains FR-INV-001–012 gaps, online-only reads and real-stock limitations.
Physical assistive technology, T1–T8/R01-T035, G1–G6, actual installation restore,
quote activation/capacity and deployment remain separate. The unrelated known
administration identity timeout is preserved; this inventory change neither
establishes its cause nor fixes it.
