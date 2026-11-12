# Saved order intake readback

## Selection and baseline

The user requested continued development on 2026-11-12. Base main is
`4e130a2f6565405e90fb725eb7116ce128cd0abf`, tree
`6fa0e94766ced8403d4aefa0cd0ee1e020e46dbb` (PR100 merged).
Coordinator-reported main CI43151532555 passed 10 checks, 27 aggregate checks,
1,425 frontend cases, 6,728 Python cases plus 58 exact skips, and 137 direct
browser cases with zero retries. Those receipts qualify that baseline only.
Historical source-authored PR99/PR100 pending fields remain historical; they do
not qualify this candidate. The earlier administration identity timeout remains
unresolved: its later pass is not a root cause or fix. No timer/fence change is
made. No higher-priority reproducible readiness defect was established here.

The concrete gap is operational: intake already records condition and accessories
in the admitted order and durable journal, but the order view never shows them.
A mechanic cannot retrieve those handoff details from the existing order UI.
This bounded completion of an existing intake slice is an independent prerequisite
under Master Loop §16 and the product alignment S2 exception, not broad V0.2
activation. Active V0.1 remains partial; physical T1–T8 and R01-T035 remain open.

## Requirements, invariant and design

FR-SVC-003 / R02-T005 remain partial: this adds saved text readback, not reception
photos, documentary evidence, full order details or a reception receipt. UX
SCR-012 and keyboard/reflow requirements apply. Existing Offline First admission
and order read boundaries are unchanged.

- Render only existing `intake_condition` and `accessories` from the already
  admitted `orders.read` projection. No customer or bicycle enrichment, IDs,
  independent query, capability expansion or second authority path.
- A native per-order disclosure labeled “Datos de recepción” works with keyboard
  and touch. Its open state is transient, not persisted. Reading never dispatches
  a mutation, transition, retry or network request.
- Preserve nonempty saved text exactly as inert React text, including line breaks.
  Wrap long words without truncating. Missing/blank condition says “No registrada”;
  missing/blank accessories say “No registrados”. These mean unrecorded, not
  “undamaged” or “no accessories”.
- Do not claim local records are server-confirmed. Existing sync and conflict
  semantics, list scope, transition guards and logout masking remain unchanged.
- No schema, migration, API, journal, receipt, quote, inventory or financial change.
  No new ADR is needed for this read-only use of the existing projection.

## Test-first evidence

Six new actual-component cases first failed on unchanged main because the
recorded fields/disclosure were absent. After implementation the focused component
suite passed 54 cases (six new plus existing history/filter controls). Independent
review found that an earlier placement before actions displaced the
Plano desktop actions column. A seventh regression case first failed, then the
disclosure moved after actions. The final focused suite passes 56 cases, including
the runtime composition case described below. This
runtime composition case creates two admitted offline orders, reloads the full
runtime against the same IndexedDB fixture, renders their saved intake, and proves
unchanged journal bytes, no network calls and logout masking. That is fake-IDB
runtime evidence, not native-browser persistence qualification.

The existing full `order-lifecycle.spec.ts` journey now checks keyboard disclosure
and saved field visibility after an actual offline browser reload. Its original
journal-preservation and server-payload assertions remain intact. Full backend
browser execution requires a dedicated PostgreSQL E2E database; no ordinary
or production database may substitute.

## Qualification and remaining gates

Final focused tests: 56 passed; frontend: 1,433 passed, zero skips; repository:
202 passed. Frozen pnpm 11.17.0 and uv installs, lint, TypeScript/mypy, formatter,
production PWA build and OpenAPI/generated-client contracts pass. The initial lint
invocation failed because uv's default cache directory was read-only; rerunning
with the supported writable cache passed. Node 24.22.1 and Python 3.13.5 meet the
project engines but do not replace pinned hosted-toolchain qualification.

Native Chromium could not start: its process-singleton socket operation was not
permitted by the local environment. No page was rendered, no screenshot or DOM,
keyboard, layout or axe evidence resulted, and no workaround/retry was attempted.
Full browser also lacks the dedicated PostgreSQL database. The authored lifecycle
and four-theme checks are collected/typechecked but remain unexecuted. Independent
source review found no further blocking issue after the action-column correction;
measured native layout remains pending. Original branding timeout is not fixed.

Final aggregate: partial, 21 passed, zero failed, five environment blockers.
Python: 6,102 passed, 685 environment skips, 12 warnings. The blockers are missing
PostgreSQL test URL, Docker, psql, managed Chromium navigation policy for the 100k
probe, and the dedicated backend browser database. Earlier aggregate passed 16
checks with eight blockers before the venv tools were added to PATH; its Python
count was 6,101 because it started before the new documentation contract. Both
receipts are preserved. The final aggregate metadata names base HEAD because the
candidate was uncommitted; it is not a fresh-main acceptance receipt. A source
SHA-256 manifest binds its checked files. Only evidence documentation changed
afterward, followed by fresh repository/format checks and diff verification.
See the execution-state checkpoint and durable receipts for the final commit/tree. No hosted candidate, full backend browser,
physical device, real installation/restore, capacity, deployment, publication or
merge is claimed by these local tests. Quote activation stays closed, inventory
stays connected-only, SPENT40927223929 and UNKNOWN41011497919 remain unchanged.
