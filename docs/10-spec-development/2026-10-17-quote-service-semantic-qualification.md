# Fixed six-node quote service semantic qualification

## Status and source boundary

Prepared only, 2026-10-17 UTC. Independent exact-source review and a separate
one-shot publication decision are pending. The authoring host's containment is
unproved: no candidate import, compilation, collection, test, formatter, linter,
typecheck, contract check, build or local runtime was performed. No branch was
published, no PR was opened and no workflow was launched for this preparation.
Data-only Git/byte/hash inspection is not runtime evidence.

The starting source is corrected-service commit
`65e2e69df4c2ad134ff2256864e44256fc5d3b3a`, tree
`6c5d5d3f2af75f505262901f8099e89f5942f50f`, reconstructed onto local baseline
`f9849cbca62311d6fe090e5800986307a223cbd9`. Product code, schema 0012, fixture
setup, lockfiles and dependency/image preparation inputs are unchanged. No
schema 0013 or effect-version admission amendment is combined here.

The only executable-source changes relative to that tree are the six string
selectors in `scripts/ci/quote_capacity_micro.py` and one stronger assertion in
an existing selected test. A new fixed workflow copies the corrected-service
recipe with only its workflow/branch/job/artifact identity and descriptive step
names changed. Documentation records prior evidence and this pending scope.

## Prior verified scope, retained independently

[Run 39041920516](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39041920516)
(job `117422972026`, run 1/attempt 1) passed on the source above. Artifact
[`12104491644`](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39041920516/artifacts/12104491644)
has ZIP SHA-256
`673a87843db6f3379472a000ddfc3f761568174f3f7afb935f8bf53c8580e78b`.
Independent evidence review accepted exactly six tests with 18 ordered successful
setup/call/teardown phases, zero collection/protocol/unhandled errors and zero
failed/skipped phases, complete scoped source/resource evidence and both final
absence receipts. These were two DTO nodes and four SQLite nodes:

- Exact closed create/applied-decision response round trips.
- Actual UTF-8 response-byte boundary and nested response revalidation.
- Creation, PARTIAL decision and exact decision replay with one complete tuple.
- Response-encoding refusal with observed count/state rollback.
- Already-expired entry refusal before writer/effects.
- Historical quote-only decision replay without an invented order transition.

Workload time including pytest bootstrap through teardown was 4.410 seconds;
setup was 2.171 seconds and supervisor time including cleanup was 7.243 seconds.
Final worker peak was 107,028,480 bytes and database peak 83,677,184 bytes.
Combined worker/database workload CPU was 4,941,034 microseconds. These are
measurements of that tiny run, not predictions or capacity/latency claims.

The canary verified its three-generation descendant-containment scenario. The
successful service run verified client reaping and final removal/absence; it did
not exercise the real service failure-marker or failure-path cancellation. No
strict stop-before-nonblocking-reap ordering is inferred. The initial failed run
`39039629649` remains failed, its discarded initiating exception remains unknown,
and the synthetic correction regression `39041234055` does not recover it.

## Exact pending selection, in execution order

All six are existing tests. Only node 6 receives the assertion described below.
This is one closed batch, not a suite, matrix, selectable framework or retry.

1. `services/platform/tests/quotes/test_quote_driver_budgets.py::test_raw_driver_budget_failure_has_availability_category`
   - A fake cursor raises `psycopg.OperationalError`; require the private
     `_QuoteDriverUnavailable` category and an empty exception string. This does
     not exercise a real driver call, HTTP error or full connection invalidation.
2. `services/platform/tests/quotes/test_quote_driver_budgets.py::test_budget_first_round_trip_can_exhaust_original_deadline`
   - The fake cursor advances a controlled clock to the original deadline on
     the first statement; require `_DeadlineExpired` and exactly the first
     `SET LOCAL lock_timeout = '2000ms'` statement. No real PostgreSQL timing is
     qualified.
3. `services/platform/tests/quotes/test_quote_application_service.py::test_false_flag_denies_new_but_preserves_exact_revision_replay[sqlite]`
   - Create once; with commands disabled, replay that same **creation** receipt,
     refuse a new revision and retain one quote operation. Despite the existing
     test name, this is not revision replay or a delivery-field assertion.
4. `services/platform/tests/quotes/test_quote_application_service.py::test_foreign_actor_and_noncustomer_decision_are_refused[sqlite]`
   - Refuse a principal with organization `b`, then create as the valid actor;
     refuse decision evidence for `customer-b` and require counts `(1, 0, 0, 1)`.
     This is a narrow scope/customer negative, not all grants/enrollment checks.
5. `services/platform/tests/quotes/test_quote_application_service.py::test_commit_ack_loss_is_unknown_and_same_identity_replays[sqlite]`
   - The monkeypatched commit first commits and then raises. Require unavailable
     with `outcome_unknown=True`; a fresh Session must replay the same decision
     while commands are disabled and retain counts `(2, 1, 1, 3)`. This models
     acknowledgment loss after SQLite commit; it is not a network-fault test.
6. `services/platform/tests/quotes/test_quote_application_service.py::test_expiry_after_order_effect_flush_rolls_back_outer_transaction[sqlite]`
   - Advance the controlled clock to 9 only after the original `append_change`
     returns, against deadline 8. Require unavailable, `assert clock == [9.0]`,
     unchanged four-table counts and order version 1. The new assertion excludes
     an earlier unavailable refusal falsely satisfying the late-phase test.
     It does not add a workload or change product semantics. Count equality is
     not a row-by-row database/association equality or a hard deadline proof.

The two pure nodes have no database fixture. The four service nodes each use
function-scoped `tmp_path/identity_migration.sqlite3`, enabled foreign keys,
cleared ambient connection settings, migration to unchanged head 0012 and the
existing two-tenant seed. Each creation uses the existing four-line quote. The
source-backed expected total is five persisted quote operations plus one late
rolled-back decision attempt, additional refused calls and tiny fake-cursor
checks. This is fixture accounting, not a measured artifact total. PostgreSQL
remains separately bounded, unused environment overhead.

## Why the selection-only change is the smallest safe option

Keep one fixed `SERVICE_NODES` tuple and the existing `--service-initial` route.
Collection order, unique count, accepted receipt identities and all 18 required
protocol phases already derive from that tuple. Replace only its six selector
values; keep supervision, parsing, limits, failure diagnostics, cancellation and
cleanup byte-for-byte. No generic selector, environment-driven choice, additional
mode, copied helper, resource increase or extra guard layer is introduced.

The legacy mode/status/artifact-path labels remain unchanged intentionally; they
name the established execution mechanism. Interpret results using the exact
source tree, new workflow identity and six retained node IDs, never the legacy
label alone. New guard SHA-256:
`8a60b0d1f7f774bf2800f72312ce40081f3f3c75d0f96e879cf4b93bb5fdce25`.
New application-test module SHA-256:
`bd7eba2b375444adc48e07af183e739f161cdd6ef400de110cb572f7c14467ce`.
New workflow SHA-256:
`d2410a6cab96c7af55c4dc3b3c9efd4f99c1a3843c45274785d77b59ffa11794`.

Every prior workflow file remains byte-identical. Prior commits and artifacts
retain their original selection. Consumed bootstrap/correction helpers also
retain their historical exact hashes; their hashes do not admit this new tuple
and must not be updated or rerun to qualify it. Those fixed gates remain bound
to their own immutable sources. This candidate changes no previous result and
is not a replacement attempt for the original six.

## Unchanged resource and acceptance plan

- Worker: 1 CPU, 512 MiB RAM, swap zero, 64 PIDs, UID/GID 10001.
- Separate PostgreSQL overhead: 1 CPU, 768 MiB RAM, swap zero, 128 PIDs,
  PostgreSQL user; no PostgreSQL application node or connection URL is selected.
  The simultaneous allocation is two separate CPUs and 1,280 MiB, not one CPU.
- Canary: same worker image and 1 CPU/512 MiB/swap-zero/64-PID limits; removed
  before the database/worker pair is started. The real descendant canary remains.
- All containers: private cgroup namespace, read-only rootfs, all capabilities
  dropped, no-new-privileges, no Docker logging and 64-MiB `/tmp` tmpfs. Database
  additionally has unchanged 256-MiB data and 16-MiB socket tmpfs. Canary/database
  have no network; worker shares only the database's isolated network namespace.
- Actual source/clean-commit, source-image label, image IDs, ownership,
  configuration, cgroup, privilege and zero-pressure checks precede selected
  imports. The environment is emptied; plugin autoload and cache are disabled.
- Aggregate setup: 30 seconds. Single workload: 20 seconds including imports,
  collection, fixture setup, calls and teardown. No timeout extension or retry.
- Combined worker/database workload CPU: at most 40 seconds; their total lifetime
  CPU: at most 60 seconds; canary: at most 10 seconds; total with canary: at most
  70 seconds. Final monotonic resource samples and arithmetic remain required.
- Final sampling: 5 seconds. Failure cancellation: 5 seconds. Supervisor cleanup:
  35 seconds. Outer supervisor TERM: 120 seconds, KILL grace 30 seconds.
  Independent cleanup step: 60 seconds (55-second internal deadline).
- Output cap: 16 KiB. Failure marker: at most 512 bytes, closed numeric fields;
  unavailable/invalid diagnostics never become fabricated success evidence.
- Image preparation remains separately bounded by two 300-second builds and a
  60-second pull, each with five-second kill grace, a 12-minute preparation step
  and a 20-minute whole job. These are preparation time ceilings, not a claim
  that image builds inherit the worker's CPU/memory containment.

Success requires exactly these six node IDs and 18 ordered successful phases,
collection/session/process success with no failures/skips/errors, exact source
and actual image/control evidence, final resources, verified client reap,
supervisor absence and the independent matching-run absence receipt. The
successful path is not itself a failure-cancellation experiment. Missing or
invalid evidence fails qualification; retain any failed/partial result.

## Publication gate and remaining work

The new `.github/workflows/quote-service-semantic-qualification.yml` accepts
only push on `codex/quote-service-semantic-qualification`, run number 1 and
attempt 1, and checks its exact workflow reference before preparation. No
manual dispatch, PR trigger or dynamic input is added. Checkout remains exact
SHA with credential persistence disabled. Artifact name:
`quote-service-semantic-qualification-${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}`.

Independent exact-tree/diff/import-closure and resource-plan review must precede
fresh remote parent/branch/open-PR/workflow-trigger checks and the separate
publication decision. A push starts execution immediately; a PR would additionally
trigger ordinary CI and is outside this preparation. A consumed, failed, skipped
or ambiguous run stops for review, without automatic retry, branch rename,
counter change, second push or widened selection.

All six selected semantics remain unexecuted for this preparation. Touched-scope
static/contracts require their own bounded gate. Full grants/enrollment negatives,
APPROVE/REJECT, wider replay/cleanup and association corruption, schema/versioned
payload admission, PostgreSQL atomicity/concurrency/real-driver timing, hard total
Python/acquisition/cleanup deadlines, HTTP/UI/ingress fences, maximum capacity,
nominal latency/contention, restore, physical devices, operator rollout and
activation remain open. This preparation changes no API or deployment state.
