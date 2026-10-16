# Bounded API restart observations

Status: **local diagnostic instrumentation; hosted evidence pending**. This is
not a demonstrated startup correction, operational qualification or permission
to rerun a workflow. The original failure and unknown cause remain retained.

## Source and retained failure

Base actual main: `fa70f896264eeb90d21b22b27cb59c5b7c6865ea`, tree
`07800a5810b71920f0a383ba4ccd51a90c325da2`, the merge of PR48. Its parents
are `51c351864cec4dbf444e5f99d3c441239a4b2665` and
`666f2ffad27b5dc0fa1d03d3902ba209eb551753`.

[Runtime run 38827236201](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38827236201)
failed on the third mandatory API restart. The first two cycles passed in
5.439 and 5.301 seconds. Cycle three failed during `waiting_ready` after
184.003 seconds. The API was recorded exited with code 143 after the intentional
graceful stop. The checked Compose start command returned successfully, but no
later API startup was present in the captured log tail. That evidence does not
establish why readiness failed, nor whether the start led to a transient process.
No Docker events or inspect start/finish timestamps, OOM flag or daemon-error
presence were captured. Seven of eleven checks completed; downstream restore,
persistence and final credential-log checks remain unqualified for this run.
Earlier source-bound passes do not supersede the failed main run.

## Narrow diagnostic contract

Only the disposable smoke harness changes. Production code, Compose settings,
images, schemas, HTTP contracts, workflows and dependency locks stay unchanged.
No new infrastructure or retry mechanism is introduced. Relevant invariants are
OPS-P04/P07/P09, minimal/private diagnostics and the security requirement that
credentials never enter retained evidence. No architecture decision changes.

Each existing cycle records these observations:

- Before stop, resolve exactly one full API container ID through the existing
  random project's Compose command. Verify its ID, exact generated project label
  and API service label through a closed inspect projection. Refuse partial,
  multiple, foreign or malformed identities; do not retry failed resolution.
- Capture inspect state before stop, after stop, after the checked start command,
  and at completion or failure, before cleanup. Retain only closed status,
  running/restarting/OOM booleans, exit code, restart count, validated UTC
  start/finish timestamps and whether `State.Error` is nonempty. Never retain
  the error string, environment, mounts, command, labels or health-check output.
- Record checked stop/start outcome and finite monotonic command boundaries.
  Successful command stdout/stderr is not persisted. A returned start command
  is an observation, not proof of a running or ready API.
- At completion/failure query Docker events with an explicit captured
  `--since`/`--until`, exact-container, generated-project and container-type
  filters. Revalidate container ID, type, lifecycle action and nanosecond time
  window. Retain only action/time and bounded numeric exit-code/signal values.
  Drop foreign events, unknown actions and arbitrary attributes. Never export
  an unfiltered event object or infer cause from exit 143, OOM or missing events.

Every subprocess reuses the existing **5-second / 16-KiB** capture, complete-output
redaction and child/process-group cleanup. Event parsing also caps at **128 rows**;
the byte cap can bind earlier. Timeout, overflow, malformed output, command failure,
invalid clock and unavailable probes produce fixed statuses without raw output.
Docker retains only its last 256 events: an empty or limited result is not proof
that nothing happened. These are finite historical queries, not subscriptions.

A full cycle uses at most six probes: one identity resolution, four inspect
snapshots and one event query. This adds six 5-second capture budgets per full
cycle, plus bounded child cleanup and process/scheduler overhead, **outside**
the unchanged readiness loop. The after-start snapshot precedes `wait_ready`;
its 180-second budget still starts inside that function. Diagnostic elapsed time
is separately reported; the existing total cycle elapsed includes observations.
Retain three mandatory cycles, no retries, 2-second readiness polling, 5-second
HTTP requests, all eleven checks and original qualification/cleanup order.
Optional collector or timing failures never skip the mandatory operations or
replace the first qualification exception.

The after-start observation can consume its five-second capture budget before
the readiness clock starts, plus existing bounded child cleanup and overhead.
This observer effect means an instrumented pass is **not temporal-equivalence
evidence** for the original run and is **not a demonstrated startup fix**.

## Local evidence and remaining gates

Fail-first evidence: 18 collector tests failed for the missing implementation;
then seven lifecycle integration tests failed while those 18 passed. The focused
suite and existing smoke contracts subsequently passed: 300 focused cases, then
598 operations/repository cases with four explicit environment skips and one
existing Starlette deprecation warning. Skips are three PostgreSQL restore cases
and the installed Node/Playwright report-privacy regression. Full Ruff lint and
format pass on 278 files; strict mypy passes on 114 source files; four changed
documents pass Prettier. Independent review has no remaining source/document
blocker: 573 operations passes/four skips, 25 repository passes and 96 additional
adversarial cases. The initial broader review found a stale one-line source-hook
assertion; it now preserves ordering and verifies the full new call. Optional
local Go-template execution was unavailable; neither these results nor static
projection checks prove actual Docker template execution.
Synthetic fixtures exercise graceful 143 stop, subsequent lifecycle/OOM events,
foreign identity rejection, invalid values and secret/JWT canaries. They do not
reproduce or explain the actual main failure.

The Python 3.13.5 environment is reused from the separate locked catalog worktree:
its entire `uv.lock` matches this base; installed pytest 9.1.1, Ruff 0.16.5,
mypy 1.20.2, Pydantic 2.13.5 and Pillow 12.3.0 match that lock. No new installation
is claimed. Existing Docker capture tests exercise small synthetic child
processes only. No Docker runtime, PostgreSQL, native browser, capacity specimen,
workflow rerun, real credentials/accounts, activation or deployment runs here.
Exact-candidate hosted collection and any evidence-led startup correction remain
separate gates requiring their own authorization. Existing maximum quote
capacity, physical-device and operator recovery gates remain open.

References: [Docker events filters, bounds and formatting](https://docs.docker.com/reference/cli/docker/system/events/),
[Docker inspect projection](https://docs.docker.com/reference/cli/docker/inspect/),
[existing local runtime boundary](../07-operations/2026-10-14-local-runtime.md).
