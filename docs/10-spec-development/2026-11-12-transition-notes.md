# Optional notes on existing order changes

## Baseline and selection

Fresh clone and remote main match PR101 main
`f1ead7e1dfe83c3ce7e740027ec4ff4d29183f47`, tree
`208bc4b8856fc5ef92cc8e597a0cf89f18a40138`. The coordinator reports main
CI43167845835 passed 10 checks, aggregate 27, Python 6,729 plus 58 expected skips,
frontend 1,433 and direct browser 137 with zero retries. This receipt qualifies
only that baseline and supersedes historical PR101 publication/browser pending
statements only for its accepted source. It does not qualify this increment.

The prior checkout did not survive the environment replacement; no old local
bytes or qualification were reused. The user requested continued development on
2026-11-12. The remaining physical V0.1 gates remain open; no new reproducible
release-gating defect was established. The original branding timeout remains
unresolved, with no timer/fence change or fix claim.

Existing state transitions, domain events, HTTP and sync already carry optional
notes, but the admitted runtime/UI dropped that input. This increment completes
that existing operational handoff path so a mechanic can explain a pause, resume,
cancellation or other existing change. FR-SVC-012/R02-T011 and
FR-SVC-016/R02-T013 remain partial. This is an explicitly bounded independent
prerequisite under Master Loop §16 and product-alignment S2, not broad V0.2
activation while physical V0.1 qualification is incomplete.

## Design and boundaries

The [design](../superpowers/specs/2026-11-12-transition-notes-design.md) records
ownership and acceptance. Notes are optional, not mandatory reasons or diagnosis,
quote authorization evidence, internal/private messages, or a new visibility tier.

- Existing legal actions, authority, actor binding, atomic journal/event write,
  conflicts and unknown-outcome protection are unchanged. No schema, API, sync
  entity, new capability, financial behavior or inventory write is introduced.
- Runtime owns at most 50 bounded per-order unsent drafts. They survive filters,
  pagination and view remounts within the same admitted scope. A scope token
  rejects old editors; logout/new scope clears drafts. They are **not persisted**.
- Editing is blocked during an outstanding or unknown transition. The note is
  captured before dispatch. Only the matching known local commit clears it;
  unknown outcomes preserve disabled text and the existing no-repeat warning.
  A known commit with unavailable view also keeps the existing action protection.
- New input uses the HTTP limit of 2,000 Unicode code points and rejects NUL/lone
  surrogates. Python whitespace collapse matches the server, including preserving
  BOM. A 4,000-code-unit UI/draft bound admits 2,000 astral characters while
  allowing bounded invalid text to remain visible and correctable. Existing
  historical notes and queued payloads are never rewritten.
- Drafts warn before voluntary session/workshop departure and before unload.
  These are best-effort warnings, not crash recovery. The UI explicitly says
  unsent notes are lost on reload. Clearing text explicitly discards only a draft.
  A draft on an order that becomes final stays visible for explicit clearing.
- Existing event notes render as inert text under orders.read, retaining the
  distinction between local attempts and server records. No new read enrichment.

## Test-first and runtime evidence

Seven owner/normalization tests first failed: missing note ownership, discarded
context, incorrect Python whitespace handling, and absent new-input bounds.
After implementation they passed alongside existing transition-protection tests.
Four UI tests first failed, with a passing read-only control. Subsequent coverage
includes actual App.onNote wiring, departure cancellation and the actual
beforeunload callback, as well as final-state draft clearing.

Runtime compositions prove one atomic offline transition note, independent order
drafts, duplicate-click exclusion, unknown postcommit retention without replay,
known-commit/unavailable-view handling, stale editors after login changes, invalid
input without journaling, refresh continuity, and saved note history after a full
fake-IDB runtime reload. Unsent drafts correctly do not survive that reload.
Eight Python reference cases confirm the unchanged server normalization/input
contract; the initial test collection import typo was corrected and retained.

The new native browser journey is authored for actual filters/remount, cancelled
logout, keyboard action, offline reload and one synced server event. Existing
four-theme journeys now interact with the actual editor, retain its mounted node
across personalization, and exercise long multiline content and narrow reflow.
These assertions are not native browser proof until executed.

## Qualification boundary

Local qualification completed with 21 aggregate checks passing, zero failed and
five environment blockers. Frontend: 1,455 passed, zero skipped/failed. Python:
6,111 passed, 685 environment skips and 12 warnings (312.10 seconds). Focused
owner/view/runtime controls: 38 passed; Python reference: eight passed; repository:
203 passed. Browser collection: 138 cases in 23 files, not executed.

Independent coordinator and reviewer source
reviews found no blocking issue. The first aggregate caught an omitted useId
declaration in the existing offline React shim; the accurate string-returning
declaration fixes the offline typecheck without changing runtime behavior. The
failing aggregate and passing corrected check are retained; the full rerun passed.
The one-line shim correction also received coordinator review.

Blockers are the absent dedicated PostgreSQL test and E2E URLs, Docker and psql,
and the managed browser policy that prevents the file-based 100k probe. The
aggregate reports the policy too broadly as blocking all navigation; its HTTP
and HTTPS exceptions remain present. No native browser launch was attempted in
this fresh environment, and no old launch denial is reused as current evidence.
Native layout/lifecycle proof is pending, not a diagnosed product defect.

The aggregate ran against uncommitted candidate bytes over the stated base, not
a merged-main commit. Its source manifest binds all runtime/test files; only
this evidence and the execution/checklist stamps changed afterward, with fresh
repository, formatting and diff checks. The retained final archive supplies the
DCO commit, tree, complete source manifest, verified git bundle and raw receipts.
This local result is not hosted or physical acceptance.

The initial full frontend suite passed 1,450
cases before the additional App/unload/final-state controls. The focused server
reference suite passed eight cases. A focused invocation after the full runner's
normal cleanup initially lacked compiled test outputs; compilation and rerun
passed. Those preparation failures are retained, not product regressions.

The new orders/lifecycle E2E typecheck is included in the normal frontend runner.
An exploratory expansion to the older structural-theme file exposed its existing
undeclared Buffer type (missing Node type declarations). The error receipt is
retained; the bounded new config does not claim to typecheck that older file.
Native browser/backend, physical, actual restore and capacity evidence remain
separate. Do not bypass browser or environment restrictions. No publication,
merge, deployment, quote activation or provider action is authorized here.
SPENT40927223929 and UNKNOWN41011497919 remain unchanged.
