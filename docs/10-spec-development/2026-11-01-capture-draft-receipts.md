# Preserve newer mounted capture drafts · 2026-11-01

Status: **implemented, hosted evidence pending**. V0.1 remains partial.
Baseline main `cdb44aac572df65489fb95a15c0a813cd5445d95`; this is a narrow
data-integrity correction to existing customer and order intake, not a new
V0.2 feature or a durable draft-storage design.

## Reconstruction and requirements

The unpublished November 1 candidates and workspace bundles were unavailable
after successive executor replacements. This November 2 same-scope reconstruction
has new bytes and requires fresh verification; no lost-commit identity or inherited
local pass is claimed. Filenames retain the original bounded plan date.

Foundation data integrity, Phase 1 `FR-CUS-001`, `FR-SVC-001` and `OFF-001`,
and the Master Loop's data-loss priority apply to the existing capture workflow.
Canonical `R01-T030` and the existing partial `R02-T005` slice supply context;
this correction does not complete every criterion of either requirement.

Controls remain editable while a local save is pending. Previously, a successful
older callback unconditionally cleared current input and promoted its old order
customer/priority selection as clean defaults. The actual TSX callback harness
executes components and outcome classification with simulated hooks/JSX and
controlled callback results. It does not exercise persistence and is not React
scheduling, native browser or storage evidence.

Each mounted form captures an opaque edit identity on admitted submission.
All 11 controls advance the identity on change. Only the unchanged submitted
draft may reset fields or promote retained defaults after a saved receipt.
Newer edits, including ABA, same-value and hidden bicycle-field interactions,
remain intact with fixed copy distinguishing the previous saved submission from
the current unsaved form. The unknown-outcome latch and synchronous busy guard
remain independent. An explicit later submission is a new intent, not deduplication.

See the [design](../superpowers/specs/2026-11-01-capture-draft-receipts-design.md)
and [plan](../superpowers/plans/2026-11-01-capture-draft-receipts.md).

## Fresh November 2 evidence and limits

- Fresh baseline RED: 20 failures / 9 passes; focused GREEN: 29 passes.
  The full reconstructed harness includes the empty-clean order-baseline case
  added after the original fix, explaining the extra RED failure. Independent
  source review accepted; copied-harness mutations removing edit markers,
  bypassing the revision fence and bypassing the submission gate failed 20,
  20 and 14 cases respectively without changing working source.
- Frontend core: 1,050 passed with no skips. Web typecheck, production PWA build,
  whole-tree ESLint, Ruff/format, mypy, offline typecheck, generated OpenAPI/client
  checks and repository verification pass. Existing bundle-size warning above
  500 kB remains; no threshold was weakened. Full local Python is pending.
- Four actual PWA browser cases are authored and freshly collected across themes;
  strict test typecheck, ESLint and Prettier pass. Native execution is pending
  hosted qualification; local E2E service/fixture prerequisites are unavailable.
  No browser, axe, screenshot or PostgreSQL pass is claimed.
- Exact-source hosted verification remains pending. The prior PR77 receipt cannot
  qualify this changed tree.

No dependency, auth/controller, schema, storage, route or deployment changes.
No guarantee across reload, navigation, reconnect unmount or process restart.
Physical T1–T8, `R01-T035`, recovery and capacity gates remain separate. Historical
cleanup `41011497919` remains UNKNOWN; ownership `40927223929` remains spent.
Pages source `3c6513d` is unchanged.
