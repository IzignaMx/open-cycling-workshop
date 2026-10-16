# Fixed online 32+1 repository profile: one-shot preparation

## Authority and source

Prepare locally from Codex commit 5813fab6863e72398d88da295707458c77b509c6,
tree 761aa77abd89f5025c4d921258e5ddfb5ec59526, equivalent to PR50 head
dd224a679db05c3ffa79fc86e1ea48c01f3feca1. Keep the final PR50 worktree untouched.
Opening the separate draft trial PR, and therefore hosted execution, requires
terminal CI50 closure and independent exact implementation/input review first.
No local Docker, PostgreSQL, large specimen construction or full-history run.

## Fixed recipe and assertions

Reuse exactly the approved single-record recipe: 80 labor charges, 10 discounts,
10 taxes; each adjustment targets the first 50 charges, for 100 lines/1,000 edges.
Preserve 500-ASCII descriptions, 2,000-ASCII note, 200-ASCII whitespace-free source
reference, prices and allocation semantics. No padding or input sweep.

Construct one initial revision and 31 revisions through real repository commands,
with fresh distinct IDs, ordinal/version preconditions and the same legal lines.
Commit each operation. While still DIAGNOSIS, attempt revision 33 and verify the
capacity error and unchanged receipts/outbox/order/head. Apply one initial full
approval to revision 32, deriving the approved set from the locked latest revision.
Verify 32 revisions, one decision, 33 logical operations, one lineage, 33 receipts
and 33 outbox records, expected head/version/sequence and totals. Verify the quote
ledger decision projection; the repository does not itself perform the application
service-order transition, so no actual online transition or lifecycle enforcement
claim is made. The production service-order row remains DIAGNOSIS/version 1 here.
Freshly reconstruct, retry original create, a middle revision and final decision;
compare exact historical receipts, current ledger equality and unchanged effects.
This tests repository/storage behavior under the accepted online lifecycle. It
does not assert implemented HTTP fencing or include restored correction histories.

Measure canonical joined bytes once per record, sum plus 32 commas/two brackets,
and raw request bytes where an actual decoder is exercised. Do not call synthetic
repository-only commands HTTP requests. Every joined record must remain <=256 KiB;
the canonical history must remain <=8,650,786 bytes (33-record universal bound)
and <=16 MiB. Preserve the exact bounded evidence artifact with numeric sizes and closed metrics
only, plus per-operation timings. Never emit raw requests, financial proof, SQL,
exceptions or pytest output.

## Deadlines and cancellation

One immutable host monotonic start T defines setup end T+20, workload end
min(T+100, actual workload start+80),
and ordinary finalization end min(T+120, finalization start+20). Setup includes source proof, owned container
creation, canary removal, actual controllers/privileges and PG readiness. Workload
includes pytest/bootstrap and all assertions, command construction, reads/retries.
Finalization includes final counters, closed result validation, removal and absence.
Every subprocess and poll uses remaining phase time. Early setup completion does
not allow borrowing extra workload time above 80 seconds. Outer timeout is 120 seconds;
its 30-second emergency grace is cleanup-only, never more specimen time.
Normal finalization cannot borrow unused workload time; its 20-second deadline
is retained across final probes, result validation and removal. Emergency cleanup
ends by min(T+150, cleanup-entry time+30); the external 120+30 cutoff remains
authoritative.

Per-operation 20-second watchdog is host-owned and includes Python construction /
validation, transaction admission, SQL and commit. Proposed minimal handshake:
the worker announces a fixed operation ordinal as ready and waits. Host records
its deadline before granting that exact ordinal. Worker performs the operation,
publishes done and waits for acknowledgement before announcing the next ordinal.
The host never accepts done after deadline and caps every probe/handshake command
by min(operation deadline, T+100). Expiry immediately attempts bounded KILL of both exact validated worker/DB IDs,
then verifies they are not running before normal owner reconciliation/removal.
Killing only the client is insufficient, as the cancellation canary demonstrated.
Stop timeout/failure remains failed/unverified and never resumes the specimen.
No reliance on matching host/container clocks or a post-hoc elapsed assertion.
Missing, malformed, skipped or illegal transitions fail closed. Repeated polling
of the same ready/done state is allowed without resetting time; a completed ordinal
cannot be replayed. Atomically replace state files and use ordinal-specific grant
and acknowledgement values, so stale files cannot authorize another operation.
Bootstrap and inter-operation gaps have an additional host 20-second bound capped
by T+100. No expensive fixture work occurs before its grant.
The handshake has no user-selected operation or workload configuration.

Keep proven worker 1 CPU/512 MiB/64 PIDs and PG 1 CPU/768 MiB/128 PIDs; no extra swap.
Lifetime CPU 240 seconds is a defensive aggregate ceiling within 120 wall seconds,
not efficiency evidence. Preserve actual pressure/identity proofs and external
owned cleanup. No budget changes on failure. No contention experiment bundled.

### Fixed operation enumeration

Ordinals 1–32: create/revise, including input construction, decode where supported,
admission, validation, DB apply, commit and joined-record numeric accounting.
Ordinal 33: attempted revision 33 with unchanged-effects assertion. Ordinal 34:
initial decision construction, admission/load, approval selection, apply, commit
and joined-record accounting. Ordinal 35: fresh reconstruction and counts.
Ordinals 36–38: exact create, revision 16 and initial-decision retries respectively.
Ordinal 39: final canonical framing/byte-bound assertions and closed evidence write.
Only tiny imports/fixture DB bootstrap may precede ordinal 1; the host gap deadline
and phase deadline cover it. There is no user-selected operation list.

## Single deliberate hosted trigger

New uniquely named workflow quote-online-once-20261016.yml, one job, no matrix.
Only pull_request types:[opened], exact trial head branch and repository identity,
github.run_number == '1' and github.run_attempt == '1'. No push, synchronize,
reopened, dispatch or schedule. Use read-only contents permission. Unique owner
token/run ID and exact archived merge tree retain existing identity checks.

GitHub documents run_number as unique per workflow run, starting 1 and incrementing
for each new run; rerunning leaves it unchanged. run_attempt increments on reruns:
https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
Thus duplicate events producing new runs skip at run_number>1; reruns skip at
run_attempt>1. A mistakenly consumed first run fails closed; do not rename the
workflow or raise the number to bypass it. Record available repository history and Actions workflow metadata before publication.
The connected metadata endpoint is unsupported; the parent explicitly accepted
that limitation because first-run/first-attempt conditions fail closed. Absence
on inspected main/local refs is not proof of absence across all repository history. Existing ordinary
CI workflows continue independently and do not invoke this batch.

## Small local TDD and review gates

- Closed mode/result schema: exact counts, finite nonnegative times, per-record
  byte caps/framing and allowed ordinals; malformed/missing/excess values reject.
- Mock immutable phase boundaries and remaining-time propagation, including a
  subprocess that exits zero after its deadline and setup exhaustion before pytest.
- Mock handshake ready/grant/done/ack; no early construction, no next operation
  without acknowledgement, expiry during validation or commit removes owned worker.
- Mock deadline expiry stops workload; only bounded cleanup continues in grace.
- Trigger assertions: only opened, exact branch/repository, run1/attempt1, one job;
  duplicate/new-run2 and rerun attempt2 cannot execute the workload.
- Existing guard suite, changed-file Ruff, strict mypy, diff/format checks. No
  selection/import path that constructs the full specimen in local validation.

Independent design review precedes code. Final exact tree/package review precedes
parent publication; CI50 closure also precedes opening the trial PR. One hosted
failure is a result requiring diagnosis/review, never an automatic repeat.

## Interpretation

QA section 25 nominal preliminary p50 <150 ms / p95 <500 ms / p99 <1 s targets still require
representative hardware/load and an explicit heavy-operation exception if relevant.
Per-operation 20 seconds is containment, not UX acceptance. Sequential full-history
reconstruction may grow quadratically or worse; the single-record timings do not
prove this batch fits 80 seconds. Capture a partial failed result if it does not.

## Established prerequisite and remaining review

PR50's corrected fixed specimen passed run
[38894594316](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38894594316)
on merge 810f9c50da3094ffd01ba25bec4359ab59bab076 / tree 761aa77abd89f5025c4d921258e5ddfb5ec59526.
Independent review checked actual limits, cancellation canary, privileges,
network/source identities, counters and final absence. Joined revision 207781 plus
initial decision 66065 plus array framing 3 gave 273849 bytes. One fixed record pair
was qualified; this larger profile has not executed. Earlier failed runs remain
preserved and are not reclassified as passing.

Accepted ADR
[online boundary §7](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md)
limits the intended initial workflow to 32 pre-consent revisions then one initial
decision. Storage's richer 128-decision allowance is distinct. This fixture invokes
repository commands; it cannot prove application/HTTP lifecycle fencing or the
actual service-order transition that those layers must implement.

Local repository history has no entry for the new workflow filename. Remote
Actions workflow-list verification is currently unavailable through the connected
read tool; its endpoint is unsupported. This is an explicitly accepted metadata limitation, not verified remote absence. First-run/first-attempt conditions remain
fail-closed even if an earlier workflow identity/run exists. Parent must preserve the first-run conditions before opening the trial PR. The parent has accepted the
metadata limitation; a skipped first run must be reported without renaming or
changing the required run number.

No hosted result or exact-tree final review exists for this preparation yet.

Host-measured durations for acknowledged operations and the active ordinal are
retained even on failure, separately from the fixture-only local timing samples.

## Whole hosted-job wall budget

The dedicated job has a 15-minute (900-second) hard wall timeout, including checkout,
image preparation, containment/workload, cleanup and artifact upload. Image
preparation is limited to 9 minutes: two 210-second build commands and a 60-second
pull, plus reserve for shell/build setup. The workload step is at most 3 minutes
and retains the stricter 120-second supervisor plus 30-second cleanup-only kill
grace. Independent cleanup and artifact upload each have a 1-minute timeout. These
step maxima do not extend the overall 900-second cutoff. Missing cleanup/artifacts
or a cancelled job cannot qualify the trial.

The 240-CPU-second observed aggregate applies to the contained canary/worker/DB
lifetimes. Image-preparation CPU is not measured by these cgroup counters and is
not included in the reported specimen CPU claim. No efficiency claim is inferred
from either hard ceiling. The original PR50 ordinary workflow remains unchanged.
