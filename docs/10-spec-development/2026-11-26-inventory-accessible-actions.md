# Inventory catalog action names · 2026-11-26

## Scope and baseline

Baseline: merged main `382fa000ebd1b72fac3a1dfc6ea60ac0df712021` (PR124).
Its [candidate acceptance and separate pending main run](2026-11-26-rest-create-id-conflicts.md#corrected-pr124-acceptance-and-merge--2026-11-26)
remain source-bound evidence for that correction, not this UI successor.
This increment addresses action naming in the existing connected inventory catalog.
It does not add inventory commands, offline stock, permissions or schema changes.

[Phase 1](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md)
ACC-001 (WCAG 2.2 AA), ACC-002 (keyboard operation) and ACC-008 (accessible names),
plus [UX §19](../04-ux-design/open-cycling-workshop-platform-phase-4-ux-ui-design-system-v0.1.md#19-accessibility),
require consistent accessible controls. WCAG 2.2 criterion 2.5.3, Label in Name,
requires the accessible name to include the visible text label. FR-INV-001 remains
partial; this corrects the existing catalog presentation rather than completing
its broader product-management requirements.

## Observed source defect and correction boundary

The product button visibly says **Consultar producto**, but its `aria-label`
contains **Consultar** followed only by the product name. For ordinary names,
that omits the visible word **producto**. Products sharing a name also receive
the same accessible action name even when their visible SKUs differ. A user
selecting an action by spoken label or an assistive-technology button list cannot
reliably distinguish those rows by SKU from the action name alone.

The bounded correction names each action **Consultar producto [name], SKU [sku]**,
including the visible label, product name and SKU in the accessible name. It uses the same already displayed text fields and
preserves plain-text escaping. The visible caption, button role/pressed state,
selection handler, focus behavior, page filtering and pagination remain intact.
Selecting either identically named product must still use that row's product ID
and display its own stock/history; the accessible name is not used as identity.

The [connected-read ADR](../02-technical-architecture/2026-10-15-connected-inventory-read.md)
remains authoritative. No API, fetch policy, authorization, local persistence,
mutation queue, ledger arithmetic or offline state transition changes. Theme
tokens, touch target sizes and existing error/freshness announcements are retained.

## Verification and documentation currency

The component regression first produced **one expected failure and six passing
controls** against the old duplicated action names. A fixture guard first failed
against the original fixture, then all **four fixture tests** passed (1.68 seconds)
after two existing visual-fixture products were given the same name while keeping
their distinct IDs and SKUs. The production action name now includes all three
text components; test-only selectors follow that exact contract. The final
component selection passed **7/7**, and the inventory E2E typecheck passed.

The four-theme browser cases distinguish these same-name products, activate them
with Enter and Space, check pressed state and SKU detail, and observe stock reads
for their actual separate product IDs. Existing accessibility/reflow assertions,
retries and timing limits remain intact. The frozen baseline PWA then produced
**one native failure with zero retries** after successful login and catalog load:
the SKU004 product action was absent under its required label/name/SKU accessible
name. The same updated test and fixture are used against the rebuilt candidate.
This directly exercises the naming regression rather than a failed authentication
or unavailable catalog. The rebuilt candidate then passed **17/17 native inventory cases** in **52.4
seconds**, with **one worker, zero retries, zero flaky cases and zero skips**.
All four themes exercised same-name/distinct-SKU actions, Enter/Space activation,
exact stock-request product IDs, selected SKU, pressed state and focus, retaining
the prior axe, touch, reflow and safety checks. The production PWA build passed
with pinned Node **22.16.0** and pnpm **11.17.0**.

Frontend core passed **1,806 tests**
with zero failures/skips (35.19-second test phase); repository contracts passed
**227 tests** (3.39 seconds), and the repository verifier passed. Independent
source review found no blocking findings and confirmed existing journey
assertions remain intact. Touched ESLint/Prettier and fixture Ruff checks passed.

Local source-bound evidence is retained separately:

- `artifacts/inventory-actions-20261126/baseline-build.json` identifies the frozen
  baseline source/build used for native RED.
- `apps/web/test-results/inventory-actions-red-20261126-report.json` records the
  missing accessible-name failure after successful login/catalog loading.
- `apps/web/test-results/inventory-actions-green-20261126-report.json` records the
  candidate's 17 passing cases. Authenticated traces remain local test artifacts.

The safe receipt `artifacts/inventory-actions-20261126/native-local-receipt.json`
binds baseline/candidate source and built assets; the final source hashes remained
unchanged through native execution. Its SHA-256 is
`59e986feb8e167c7da0c0fdd1331e99051fc55196a003201ef1b0fd6acfb6531`.
The owned PostgreSQL test container was removed and its label/container absence
confirmed. Final E2E type, lint and fixture Ruff checks passed again.

These passing invocations overlap and are not additive unique-case totals.
Exact successor hosted qualification remains pending; the main PR124 run remains
separate from this accessible-name candidate.

The inventory feature README still described four-theme browser scenes as authored
but not locally executed. The [November 25 inventory audit](2026-11-25-project-inventory-audit.md)
already records **17 local native cases with zero retries** for its dated source.
That historical local result now has an explicit reference in the feature README;
it does not qualify this later accessible-name change automatically.

## Remaining gates

V0.1 remains **partial**. Physical screen-reader/voice-control, Windows/Android,
T1–T8/R01-T035, G1–G6, real stock reconciliation, installation restore and deployment
are not established by synthetic browser results. All FR-INV-001–012 gaps remain
in the [inventory scope table](2026-11-25-project-inventory-audit.md#inventory-requirements-retained).
There is no new installed instance or changed workshop data in this increment.
