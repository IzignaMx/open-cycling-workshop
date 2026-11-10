# Bounded frontend diagnostic retention · 2026-11-09

Status: **locally verified and independently reviewed; unpublished; original main failure unresolved**.
Base main `ba831f84575cfb04ce325ad72c1b4f7a28f3bebe`, tree
`f91656894aabf7f504735f430efce32817167964`.

## Observed problem and evidence boundary

[PR97](https://github.com/IzignaMx/open-cycling-workshop/pull/97) was integrated
only after its exact-source review and all 11 checks in five workflows passed on
attempt one. PR CI42551780338 qualified 27/27 aggregate checks, Python 6,697 plus
58 exact intentional skips, frontend 1,403/API one and direct/aggregate browser
136/136 each. The published tree exactly matched the reviewed local candidate.

The separate [fresh main CI42556226651](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42556226651)
failed on attempt one: aggregate 26/27, with `frontend_core_tests` reporting
1,402 passed and one failed case in its second frontend invocation. Its first
frontend invocation passed all 1,403. The verifier retained only the final 4,000
characters of captured output. Neither the qualification artifact nor the complete
job log identifies the failed case. Its identity and cause remain **unknown** and
**not resolved**. This task must not relabel that run as accepted.

Main Python/PostgreSQL passed 6,697 cases plus 58 exact intentional skips, zero
unrun, with source, coverage and both container-cleanup records verified. Direct
and aggregate browser each passed 136 cases on their first attempt. Repetitions
20/9/5/10 and kernel 14 passed; auxiliary workflows and small proofs were inspected.
The full browser archives matched their byte counts/digests; structured details
were inspected, not screenshots/video/traces. Build-resource cleanup and
proxy-error correlation IDs remain unqualified. These results do not override the
failed frontend check or qualify a new diagnostic candidate.

## Bounded local diagnosis before this change

Two complete frontend runs on Node 22.16.0 passed 1,403/1,403 each with zero skips
or cancellations; frozen dependencies were verified with pnpm 11.17.0. Those passes
do not identify or resolve the hosted failure. A deterministic synthetic subprocess
case independently reproduced diagnostic loss: an early failure/assertion in
9,916 characters disappears when only the last 4,000 are retained, while nonzero
exit correctly remains failed. No actual failing hosted test is inferred from it.

## Intended correction

Improve only the frontend aggregate diagnostic path. Retain bounded source-file
locations and final numeric counts from structured Node test events, rather than
parsing arbitrary TAP/stdout markers. The temporary report is diagnostic transport,
not authenticated telemetry or independent workload qualification. Validate a
closed schema and known source-file identities before presenting diagnostics.
Process exit remains the authority for pass/fail. Missing, malformed, incomplete
or oversized diagnostics must be explicit; never invent the missing case or turn
a failing process green.

Avoid new public raw logs, arbitrary test titles, assertion values, stacks,
console/stderr/environment data or secrets. Preserve current Check/schema and
unrelated check behavior. Ordinary developer frontend runs remain unchanged.
The aggregate path now discards raw compiler/test stdout and stderr rather than
capturing it in memory or copying it into public diagnostics. A compiler failure or
missing report therefore produces unavailable diagnostics while retaining failure.
This privacy boundary applies to this aggregate path, not ordinary developer runs
or unrelated existing check output.

## Candidate limits and focused validation

`apps/web/tools/aggregate-test-reporter.mjs` consumes structured Node events.
`apps/web/tools/run-core-tests.mjs` selects it only when the verifier supplies its
private report destination. `scripts/ci/verify_v01.py` independently validates the
closed report and source allowlist. No workflow command, dependency or application
runtime changes. The temporary report is removed after consumption.

- At most eight failure-event locations are retained. Nested parent failures count
  separately; the final Node counters remain separate from the retained-event count.
- Source paths are allowlisted from the current frontend runner and limited to 200
  characters. Unavailable file/line/column identity is null; no arbitrary title,
  assertion value, exception, stack, console output or environment value is emitted.
- Seven final numeric counters are bounded to 9,999,999 each; a missing final
  summary remains null. The omitted-event counter saturates with explicit overflow.
- Report reads are below 8,192 bytes; serialized output is tested below the existing
  4,000-character limit. Malformed/oversized reports remain unavailable.
- Final symlinks and FIFOs are refused. If secure-open capabilities are unavailable,
  diagnostics remain unavailable instead of weakening the open or aborting the
  verifier. Actual Windows execution is not qualified.

Observed RED preceded implementation for raw secret-canary exposure. Genuine
Node 22 fixtures also reproduce an early/nested failure disappearing from the old
long TAP tail and demonstrate preserved source locations and final counts with the
new reporter. Regression coverage includes nested/multiple failures, overflow,
missing/malformed reports, control/path traversal, forged stdout, secret-shaped
8.8 MB output, symlink/FIFO refusal, missing secure-open capabilities, nonzero/zero
exit compatibility and unchanged unrelated checks.

Focused validation: 27 new diagnostic cases plus 203 existing verifier cases
passed. Independent review passed 279 cases including the 49 documentation
contracts, with exact Node 22.16.0 and the frozen Python environment. The review's
portability finding was corrected and re-reviewed. Ruff, touched JavaScript
lint/format and whitespace checks passed. A real full frontend invocation through
the new reporter passed 1,403 cases, zero failures/skips; it preceded only the
secure-open-capability correction. The final aggregate below covers that correction.
None of these results identifies or resolves the original hosted failing test.

## Final local candidate validation

The frozen implementation and all tests then completed the full local verifier:
21 checks passed, zero failed, five environment blockers. Python passed 6,098
cases with 685 environment skips and 12 warnings in 384.01 seconds; the actual
local interpreter is Python 3.13.5, not the hosted pinned 3.13.14 environment.
Frontend passed 1,403 cases, zero failures/skips, through the new structured
reporter with diagnostics available and raw output omitted. API client one,
Ruff, formatting, mypy (126 source files), ESLint, Prettier, OpenAPI/TypeScript
contracts, HTTP smoke and PWA build also passed.

The five blockers remain PostgreSQL integration (no dedicated test URL), Docker
CLI, PostgreSQL tools, IndexedDB 100k (managed Chromium URLBlocklist) and browser
E2E (no dedicated database URL). No browser restriction was bypassed. These are
local partial results, not qualification in the hosted environment.

The full aggregate was run against the uncommitted candidate on base main
`ba831f84575cfb04ce325ad72c1b4f7a28f3bebe`; its metadata records that base HEAD,
not proof that the base itself passed or that the candidate was already committed.
The implementation/test hashes were frozen before the aggregate and verified
after it. Only evidence wording was stamped afterward; all 198 repository tests
passed again against that final documentation. Independent focused source review
accepted the privacy, bounded-output and process-status behavior without remaining
blocking findings. This is not independent proof of the original failure's cause.

## Scope limits

No workflow rerun, additional publication or deployment has occurred. This local
preparation has no publication authorization. A separately approved candidate
requires its own checks; passing future diagnostics cannot retrospectively recover
the original failed case. V0.1 and FR-SVC-016/R02-T013 remain partial. Physical
T1–T8/R01-T035 remain omitted, not accepted; M2/capacity and real-data restore are
not authorized. SPENT40927223929 and UNKNOWN41011497919 remain unchanged.
