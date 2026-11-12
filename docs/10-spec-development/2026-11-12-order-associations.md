# Saved-order customer and bicycle readback

## Baseline and scope

Fresh local fetch matches main `f09441c5dcd9aee721af92471ed836528c595668`, tree
`97ddba7b1dc66183a472f2393af8ec30984bf9be`. The coordinator reports PR102 main
CI43214125482 passed 10 checks, aggregate 27, Python 6,738 plus 58 exact expected
skips, frontend 1,455 and browser 138 with zero retries. This reconciles historical
pending PR102 statements only for that accepted baseline, not this increment.
The prior clean checkout was preserved and a separate worktree created.

The [design](../superpowers/specs/2026-11-12-order-associations-design.md) records
why read-only associated identities are the bounded next workshop prerequisite
and why existing-bicycle intake needs a separate recovery compatibility design.
An isolated Dexie v8/v9 reopen reproduction is retained. No existing capture
format, database version, sweeper, REST relationship rule or financial gate changes.

An explicit order action shows its associated customer name and bicycle
brand/model with identifiers, each behind its independent read capability.
Unavailable local data is not absence. No contact fields or cross-scope lookup
are added. One volatile snapshot is invalidated on refresh and scope/session
change; an order-version/reference recheck prevents publishing an obsolete
relationship. The view explicitly distinguishes this from current server state.

## Evidence

Three runtime tests first failed because the readback API was absent. Six UI
cases first failed because the controls/readback were absent. Corrected focused
cases cover actual App callback, denied reads, revocation, pending local bicycle,
missing/blocked/absent association, retry, stale refresh/logout completion,
read-only journal/network invariants and fake-IDB reload. Preparation/fixture
errors remain in the receipts rather than being reported as product failures.

Explicit close invalidates pending reads, keeps aria-controls/expanded coherent,
and returns keyboard focus to the persistent trigger only after an explicit close.
Refresh, revocation and another order do not request focus. The initial aggregate
was superseded when that accessibility correction changed source during the run.
It exposed an existing blanket source ban on useRef in OrderList. The focused
reproduction confirmed only the two new DOM/focus refs were involved. The test
now enumerates those permitted refs and inspects the actual transition handler
to retain host-only admission and no component transition gate. Both failed and
corrected receipts are retained; no runtime protection was relaxed.

Final frozen local aggregate: 21 checks passed, zero failed, five environment
blockers. Frontend: 1,483 passed, zero failed/skipped. Python: 6,112 passed,
685 environment skips, 12 warnings (314.29 seconds). Repository: 204 passed.
New association controls: 14 runtime plus 14 UI cases. UI focused regressions:
81 passed. Transition-protection feedback suite: 20 passed after the precise
AST test refinement. Native browser collection: 139 cases in 24 files.

The five blockers are absent dedicated PostgreSQL test and E2E URLs, Docker,
psql, and managed policy preventing the file-based 100k probe. The aggregate's
policy message is broader than reality: HTTP/HTTPS exceptions remain. No native
browser launch was attempted and no prior launch failure is reused as evidence.
Only evidence/checklist/execution stamps changed after this frozen run; fresh
repository, formatter and diff checks follow. The source manifest binds the
runtime/test bytes; the final archive supplies the DCO commit/tree, verified git
bundle and retained raw receipts. This is not fresh-main/hosted acceptance. Native E2E is authored for keyboard action,
offline reload, all four themes and 320px layout, not yet executed. No timer or
branding-fence change is made; the historical branding timeout remains unresolved.
Physical T1–T8, R01-T035, M2/capacity, actual restore and quote activation remain
open. SPENT40927223929 and UNKNOWN41011497919 are unchanged. No publication,
merge, deployment, provider action or new credential is authorized by this step.
