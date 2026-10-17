# Initial six-case quote service candidate

2026-10-17. Source reconciliation only. No service import, collection, compilation,
lint, typecheck, test, Docker launch, commit, push, pull request or deployment was
performed for this candidate. All six service cases remain unexecuted.

## Source identity and preserved history

The main source is commit `8a7eeecc39b0a43097484d10dc30af541ae38156`, tree
`323661ade5a3540f389bfb5b965d4ff63b400d5c`. The local baseline commit
`f9849cbca62311d6fe090e5800986307a223cbd9` has that identical tree but is not the
actual-main commit. The exact published 11-file guard payload was reconstructed
first and its resulting tree checked against
`400a69cbd2c0351ee1ad853826e98481b41adf27`, published commit
`d481d5b68240aca635e6ded957e660481b52c06b`.

The frozen 16-file service package was verified against its original manifest
SHA-256 `dd4cb6f0206c194dc56899ee0d867133cbb559b788b0e6997622e6bb72a6a03a`.
Its twelve Python source/test files were copied byte-for-byte. Its three shared
history files were merged additively with newer main/guard evidence, and its
scope document now distinguishes the original preparation from this update.
No semantic source correction is included. Source changes between the frozen
service base and current main were documentation only.

The guard supervisor, service workflow, guard tests, bootstrap wrapper, frozen
baseline helper/provenance and consumed bootstrap workflow are unchanged from
the published guard package. PR51, PR56 and ordinary workflow definitions are
unchanged. The local package manifest and Git tree, recorded outside the tree to
avoid a self-referential hash, bind the final reconciled bytes for independent
review. A later publication must preserve that exact tree and use the verified
actual remote parent; the local baseline commit is not a remote identity claim.

## Evidence boundary

Bootstrap [run 39007201961](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39007201961),
job `117321985962`, artifact `12091531428`, run 1/attempt 1, passed 34 finite guard
cases. Four cases use tiny real subprocesses (output overflow, sleeper, shell
probe, exit-7); other guard simulations are mocked. Separate actual source/image,
cgroup, privilege and three-generation cancellation-canary evidence and both
supervisor/independent cleanup receipts were reviewed. Artifact SHA-256:
`294fa6b0a709794eb62e6675db4d426b1d96eb3b68ee19eb60dcb9527071ef60`.

That result verifies the unchanged guard source, not service behavior. No service
case, full toolchain, PostgreSQL application behavior or capacity is qualified.
The first six-node service result must be labelled initial candidate qualification;
never invent historical RED/GREEN for tests that were authored but not executed.

In service mode, cancellation precedes blocking client waits, diagnostic reads
and ownership reconciliation. Nonblocking Popen.poll() can reap an already-exited
client. The separate bootstrap's stricter WNOWAIT ordering is not claimed for the
service supervisor. The 20-second acceptance ceiling retains bounded cancellation
grace and does not promise instantaneous termination during a stalled Docker daemon.

## Exact initial selection

One invocation, in this order, with the unchanged closed selector:

1. `services/platform/tests/quotes/test_quote_command_response.py::test_create_and_applied_decision_round_trip_exact_closed_fields`
2. `services/platform/tests/quotes/test_quote_command_response.py::test_encoder_revalidates_nested_bypasses_and_checks_actual_utf8_bytes`
3. `services/platform/tests/quotes/test_quote_application_service.py::test_create_decide_replay_commits_one_complete_tuple[sqlite]`
4. `services/platform/tests/quotes/test_quote_application_service.py::test_response_failure_rolls_back_all_decision_effects[sqlite]`
5. `services/platform/tests/quotes/test_quote_application_service.py::test_expired_deadline_refuses_before_writer_or_effects[sqlite]`
6. `services/platform/tests/quotes/test_quote_application_service.py::test_historical_quote_only_decision_replay_does_not_invent_transition[sqlite]`

No collect-only discovery, second invocation, arbitrary selector, timeout increase,
fixture enlargement, automatic retry or broad suite is authorized by this document.
The collection hook must observe exactly these six ordered, unique identities.
Acceptance requires all setup/call/teardown outcomes, process/session success,
closed resource observations and both cleanup proofs, not six passing calls alone.

## Repository import closure and finite fixtures

The source-reviewed closure consists of the selected two test modules, the two
applicable conftests, explicit `scripts.ci.quote_capacity_micro` plugin, and their
repository imports. The selected service test module imports the identity/repository/storage
helpers. Those reach `test_identity_migration`, `test_quote_repository`,
`test_quote_schema` and `test_quote_storage`. Migration setup additionally loads
Alembic env, versions 0001 through 0012 and the finite ORM registry. Exact paths,
hashes and import edges are frozen in the accompanying import-closure inventory.
This is static repository-source evidence, not an observed runtime module trace;
third-party dependencies remain bound by unchanged pyproject/uv.lock and the
future source-labelled image.

Import-time decorators are included in review: two small DTO dictionaries, tiny
four-line quote constructors used by helper parametrization, two small evidence
objects, short fixed lists/maps and bounded invalid strings. They do not execute
unselected test bodies. The 101-line/large-edge/history-loop/16-MiB specimens in
`test_quote_storage` remain uncalled function bodies. No atomic-effect test,
single-pass test, frozen reconstruction oracle, profiling suite or 100-line
specimen enters the selected call path. Adding the operations directory to
sys.path in the quote conftest does not import or collect that suite.

Nodes 1–2 use handcrafted DTO dictionaries and a response-limit monkeypatch
based on that small response's actual byte length. They use no DB fixture.
Nodes 3–6 each obtain one separate temporary SQLite file, run the unchanged
0001→0012 migration chain, seed two synthetic tenants and update the one fixture
actor's grants. Each tenant has one organization, two locations, one user, one
customer, one DIAGNOSIS order and one product. No real installation is touched.

Each nonempty lineage has one revision, four lines (labor, part, discount, tax),
four target edges, and at most one PARTIAL decision approving one charge line.
Expected final quote-operation counts, not measured results, are:

- Node 3: two operations; exact replay adds none; one order event, one change,
  three outboxes. The accepted order version is 2.
- Node 4: one committed creation; one attempted decision and all its order/change/
  outbox effects roll back after injected response refusal; order stays DIAGNOSIS.
- Node 5: zero quote operations or effects; an expired deadline refuses before
  writer admission. Setup seed rows remain ordinary fixture data.
- Node 6: two repository-only historical operations; replay adds none and leaves
  order DIAGNOSIS with a null order-effect tuple and two quote outboxes.

Across four isolated databases: five persisted quote operations plus at most one
rolled-back decision attempt. There is no revision chain, history loop, capacity
or latency experiment, production data, HTTP request, account or enrollment.
PostgreSQL is started only as retained containment-environment overhead; the
four selected database cases are SQLite, so no PostgreSQL service claim follows.

## Unchanged schema and budgets

All migration files, Alembic configuration, ORM quote models and registry stay
identical to current main. Head remains 0012. The frozen service's populated
order-effect tuple matches that schema without an order_effect_version marker.
Schema 0013, bounded-read/version admission and any future historical-version
policy are excluded; combining them later requires a separate reviewed patch.
No silent backfill, guessed version or new admission limit is included.

The unchanged service guard retains: worker 1 CPU/512 MiB/swap 0/64 PIDs,
PostgreSQL 1 CPU/768 MiB/swap 0/128 PIDs, nonroot/read-only/capability/network
controls, 30-second aggregate setup, one 20-second workload including import
through teardown, 40 workload CPU seconds across worker+DB, 60 lifetime CPU
seconds across worker+DB plus 10 canary CPU seconds, 5-second final sampling,
5-second cancellation, 35-second supervisor cleanup, 120-second outer TERM plus
30-second KILL grace, 60-second independent cleanup and 16-KiB output caps.
Image preparation remains separately bounded. Neither the two-container CPU
allocation nor PostgreSQL overhead should be reported as one aggregate CPU.

## Remaining prerequisites and stop conditions

1. Independent exact-tree/package/import-closure review and parent acceptance.
2. Fresh remote parent/branch/open-PR/workflow-trigger preflight and explicit
   one-shot publication decision. Push to `codex/quote-service-contained-initial`
   launches the closed workload immediately; publishing is execution. No PR is
   created implicitly and no main push or ordinary CI launch substitutes for it.
3. First-run/first-attempt gates remain fixed. A consumed, skipped, failed or
   ambiguous result stops for review; no renamed workflow, increased counter or
   replacement push is implied. The already-consumed bootstrap is never rerun.
4. Review the downloaded closed artifact against actual run/attempt/commit/tree/
   image/source and final resources; require both cleanup receipts. Preserve any
   failure without automatic repeat. Any semantic fix first needs source review
   and its own bounded regression proposal.

Successful initial qualification would cover only these tiny DTO/SQLite service
cases. Full APPROVE/REJECT and enrollment negatives, effect-version/payload
admission policy, PostgreSQL atomicity/concurrency/driver deadlines, hard total
Python/acquisition/cleanup bounds, static/contracts, HTTP/sync/inventory fences,
UI, maximum capacity, nominal latency/contention, restore, old-writer rollout,
physical devices, operator gates and production activation all remain open.
