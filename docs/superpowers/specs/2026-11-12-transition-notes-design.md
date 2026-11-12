# Optional notes on existing order transitions

Base: PR101 main `f1ead7e1dfe83c3ce7e740027ec4ff4d29183f47`.

## Scope and selection

FR-SVC-012/016, R02-T013 remain partial. Existing transitions already support an
optional event note in the domain, API and sync envelope, but the operational
runtime/UI never supply one. Completing this existing handoff path is an
independent workshop prerequisite, not quote activation or broad release progress.
V0.1 physical gates remain open. The historical branding timeout is unresolved.

## Invariants

- Optional note belongs to one order and the next explicitly clicked legal action.
  No new action, required reason, standalone diagnosis, quote authorization,
  financial effect, visibility tier, capability, schema or sync entity.
- Reuse the existing atomic transition command/event and authenticated actor.
  Match Python whitespace collapsing, reject NUL/lone surrogates and limit new
  input to 2,000 Unicode code points, matching the HTTP transition input bound.
- Runtime owns at most 50 unsent notes, each bounded to 4,000 UTF-16 code units.
  Invalid length/text remains editable with clear feedback; never silently send it.
  The UI's native input bound is 4,000 code units, not a promise of 4,000 characters.
- A captured scope token prevents stale editors from writing into a newer session.
  Filtering, pagination and view remounts do not discard notes. Scope changes,
  logout and a new visit clear them. No persistence or reload recovery is claimed.
- Existing double-click and unknown-outcome protection remains authoritative.
  Editing is blocked during/after an unresolved transition. Snapshot the note
  before dispatch; clear it only when the matching attempt reports a local commit.
  Unknown outcome retains disabled text and the existing no-repeat warning.
- Session/workshop navigation and beforeunload warn about unsent notes. Explicit
  field clearing discards a note without changing the saved order. Browser warnings
  are best-effort; explain that these unsent drafts are lost on reload.
- Read existing event notes as inert text under orders.read, without calling them
  private/internal or proof of server acceptance. Read-only users get no editor.

## Acceptance

Observe RED/GREEN for normalization/length, per-order ownership, duplicate clicks,
unknown outcomes, stale callbacks, scope reset, draft capacity and success clearing.
Prove actual offline journal/event payload and unchanged note after reload, with
no automatic resend. Test current runtime composition, history rendering, view
filter/remount continuity, labels and navigation guards. Author native keyboard,
reflow and offline/reload/convergence assertions; report unexecuted environment
checks honestly. No deployment/publication is included. This design reuses the
accepted admission/journal boundary and needs no new architecture ADR.
