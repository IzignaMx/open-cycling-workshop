# Quote capacity prerequisite: contained microfixture only

## Decision and scope

Base `3cc611e8f5cff8a0eb5c3bc40c8ae862e7eecf81`. This is a finite
preflight for the accepted quote persistence ADR §5.1, not maximum-history
qualification or a new application deadline. No maximum specimen, mode, parameter
or fixture generator is included. Review the preflight and actual hosted
microfixture evidence before separately deciding whether to implement or execute
maximum cases. The prior 111-operation/~8.4 MB exploratory preflight remains
failed; the subsequent local guard stopped before spawn. Local Docker and
cgroup-controller proof are unavailable. Do not bypass that refusal.

The only new domain fixture creates one four-line revision, revises it once,
records one partial decision, reloads in a fresh transaction and exactly retries
the historical create. It verifies two revisions, one decision, three immutable
operations/outbox effects, unchanged replay effects and exact receipt/current
ledger. It runs only after a dedicated cancellation canary and both workload containers
pass actual containment readback.
Ordinary test collection explicitly skips this hosted-only case.

## Finite containment contract

The dedicated ordinary `ubuntu-latest` job archives the exact checked-out Git
commit, builds the existing pinned platform Dockerfile's build stage, then adds
locked development dependencies and repository test helpers. No production image
or dependency lock changes. Git commit/tree, a clean checkout, worker source-tree
label and resolved image IDs must agree. No arbitrary local files enter the
archived build context. All containers remain disposable and unpublished.

- Worker: one CPU quota, 512 MiB memory, zero additional swap, 64 PIDs.
- PostgreSQL 18.4: one CPU quota, 768 MiB memory, zero additional swap, 128 PIDs,
  20 connections and 64 MiB shared buffers. Data is a bounded disposable tmpfs.
- All three containers (canary, database, worker): private cgroup namespace,
  read-only root, dropped capabilities and no-new-privileges. Read back effective
  UID (nonroot, exactly 10001 for workers), CapEff=0 and NoNewPrivs=1 from a closed
  process-status projection. No writable checkout or Docker socket mount.
- PostgreSQL has `network=none`; the worker joins that exact container's network
  namespace. The database remains loopback-only and uses the existing safe
  `_test` URL, unique-schema migration/cleanup and fixture admission helpers.
- Read `/proc/self/cgroup` plus actual cgroup-v2 memory/swap/CPU/PID limits,
  memory current/peak, CPU statistics, memory events and PID events inside each
  exact identified container before importing the microfixture. Missing,
  malformed, unlimited or mismatched values refuse execution. Any memory/PID
  pressure event or backward CPU counter refuses qualification.
- Before PostgreSQL or the domain fixture, an identical bounded worker with no
  network spawns one fixed parent/child/grandchild chain of finite 60-second
  sleepers. After the grandchild signals readiness, kill and reap the host
  `docker exec` client. Observe only PID/PPID ancestry to prove its descendants
  remain; check final cgroup pressure/CPU (at most 10 CPU seconds), remove the
  exact canary container and verify absence. Only then may the microfixture
  proceed. This is cancellation proof, never a CPU/OOM/fork stress test.
- The host supervisor lives outside all container cgroups. Each Docker client call has a
  short deadline and a 16 KiB hard output-file ceiling via `RLIMIT_FSIZE`;
  ceiling-sized/truncated output is refused. Raw Docker errors, environment,
  pytest output and financial evidence are not uploaded.
- During the microfixture, the supervisor checks both cgroups. Each observation
  inherits the remaining whole-workload deadline. Sum lifetime CPU usage across
  workload containers against a 600 CPU-second safety ceiling; also include the
  completed canary CPU before accepting the report. Quota is a rate limit,
  not that cumulative budget. Record workload-relative CPU separately and reject
  worker process CPU exceeding its containing cgroup's lifetime CPU.
- The microfixture, including pytest import/migration/bootstrap, has a **20-second
  whole-workload watchdog**. Every measured domain operation separately checks
  below 20 seconds. A bootstrap timeout is an unqualified probe, not a product
  latency result. There is no retry or automatic budget increase.
- Setup is separate in evidence: PostgreSQL readiness is bounded to 30 seconds;
  host `timeout` caps the complete supervisor at 120 seconds, with 30 seconds
  for termination cleanup. The internal total 900-second safety ceiling does
  not authorize using that much time for this three-operation probe. Build/setup
  has separately finite step and subprocess deadlines; the entire job is 20 min.
- On success, failure or SIGTERM, remove exact owned container IDs in reverse
  creation order. Before any create, persist a random ownership token with the
  exact allowed images/names. Docker cidfiles and an ownership-filtered daemon
  listing recover IDs after create-client failure; verify exact label/image/name
  tuples before removal. A timed-out/ambiguous create remains cleanup-unverified
  even if currently known containers are absent, because the daemon could finish
  later. Independent cleanup reconciles the ownership label again; never turn
  this uncertainty into a passing report.
  Cleanup must obtain a successful strictly validated full-ID container listing
  and verify absence. An inspect error is never absence. Failed removal/observer
  failure prevents a passing result. An independent `always()` job step repeats
  owned-ID cleanup if the supervisor is killed. Runner disposal remains the last
  boundary if the daemon/job becomes unavailable; no clean-state claim then.

The emitted JSON is closed for financial result metrics and contains only source
identity, bound container/image identities, enforced limits, counters, small
operation timings, phase/status and cleanup proof. `maximum_capacity_qualified`
is always false. A passing workflow cannot authorize maximum execution.

Docker semantics checked against official documentation:
[resource constraints](https://docs.docker.com/engine/containers/resource_constraints/),
[container run](https://docs.docker.com/engine/containers/run/), and
[isolated networking](https://docs.docker.com/engine/network/drivers/none/).
Equal memory/memory-swap requests mean no extra swap; actual `memory.swap.max=0`
is mandatory. Unsupported controls stop this proof rather than relax it.

## Product acceptance still open

The existing shared PostgreSQL fixture configures 15 s lock timeout and 20 s
statement timeout; the microfixture reads both back. These are test-fixture
values, not generic application defaults. The repository's production engine and
writer admission do not set a quote-wide timeout. PostgreSQL statement timeouts
cannot bound Python reconstruction while an organization lock is held.

Twenty seconds is only a provisional worst-case technical test ceiling. It is
not an interactive-UX target, a production SLA or acceptance of twenty seconds of
tenant blocking. `QuoteRepository.load` uses writer admission and order/lineage
locks. Before activation, measure ordinary read/command time, same-organization
contention and unrelated-organization independence; an excessive hold may require
implementation changes. This minimal microfixture does not claim those results.

A separately reviewed maximum proof must retain all accepted bounds: 32 revisions,
128 decisions, 100 lines/1,000 target edges per revision, 256 KiB per canonical
result/proof record and 16 MiB complete canonical history. Choose valid count/
complexity and byte-boundary fixtures; quantify any structurally unattainable
exact byte boundary rather than relabel a smaller fixture. Exercise real
repository append, strict fresh reconstruction before pagination, immutable
reads and historical retries. Independently show that a count limit does not
prohibit another operation fitting every other limit. MAX+1 and injected failures
must leave all six quote tables and all order/change/outbox effects unchanged.
Retain real PostgreSQL restore, incarnation rotation and unchanged replay effects.
Neither a large string serializer rejection nor cumulative fixture construction
latency substitutes for any of these cases. Do not raise SQL timeouts or weaken
financial reconstruction to pass. Routes/UI, all-ingress enrollment fences,
fresh authority, atomic application effects and operator rollout remain gated.

## Local evidence and remaining verification

The missing runner was observed red at test collection before implementation.
Three additional canary regressions were observed failing for zero/duplicate PIDs
and malformed process rows, then passed after explicit fail-closed validation.
Small local tests exercise controller/counter refusal, exact shell delimiters,
CPU monotonicity, successful and failed cleanup, ownership-manifest validation,
ambiguous create refusal and cidfile recovery, observed privilege boundaries,
preflight-before-spawn, whole-workload deadline refusal, bounded output and closed
report privacy. A 50 ms sleeping-process test is bounded and creates no load.

Final focused source/mock and repository contracts: **67 passed, one explicit
hosted-PostgreSQL skip**, one existing Starlette deprecation warning. All three
changed Python files pass Ruff lint/format; direct strict mypy passes for the
one touched runner (no suppressions). Five changed Markdown/YAML documents
pass Prettier. `git diff --check` is clean. These are local results only.

Local Python 3.13.5 / pytest 9.1.1 / Ruff 0.16.5 / mypy 1.20.2 reuse the existing environment;
no installation or container execution. Its complete uv.lock matches this source,
SHA-256 `4439fc18e440130de10912aecf5a0cb7b18d4a27714e1c4fc20ccb4a4011febb`. Actual cgroup enforcement, Docker templates/network/user
semantics, PostgreSQL microfixture, cancellation cleanup and hosted source-bound
artifacts remain **pending** until ordinary CI executes this exact source.
No maximum history, restore-at-maximum, HTTP/UI or production activation was run.

## Previous checkpoint, distinct from this proposal

PR49 is merged at the base above, tree
`edf7b883454bf2a22ab6090b5dd81d76dd27acfc`. Independently reviewed actual-main
[CI 38851974896](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38851974896)
passed 27 controls; each Python run had 3,665 passes/29 explicit skips, frontend
912 and API client 1; all 218 browser executions passed at retry 0. Dedicated
PostgreSQL inventory 43 and quote/branding wrapper 24 passed.
[Runtime 38851974923](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38851974923)
passed 11/11 for the instrumented sequence, cycles 8.105/8.071/8.113 seconds
including diagnostics 0.153/0.149/0.148; restore/authenticated/branding recovery,
native ARM decoder and three builds passed.
[Security 38851975064](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38851975064)
passed. [QEMU 38851974945](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38851974945)
failed, NON-QUALIFYING. None of this proves physical Raspberry suitability.
Original main48 Runtime 38827236201 remains failed 7/11 with unknown cause; an
instrumented pass neither establishes temporal equivalence nor demonstrates a
startup fix. These historical checks are not this microfixture's evidence.

## First hosted preflight failure and bounded correction

[Run 38889970654](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38889970654)
checked out synthetic merge `1e355eec0c57b0a59967bce7908486088fe2fdc3`,
whose tree `ebe77300083a188d57b23751f2e8a31e3d2ca478` equals reviewed PR50
head `960edf9813541bb98c94ab389d733dd26598c4e9`. Image builds succeeded.
The guard failed closed after 0.223 seconds, `command_failed` before source-tree
recording. Independent cleanup succeeded; no canary or PostgreSQL microfixture
was reached. Absence at cleanup does not prove the cancellation canary.
Artifact 12040749556 ZIP SHA-256 is
`8ccdb7fa5ecf4d84d40a39b7f488cb3ad10408f82a11821e15650e380c03eba3`.

A bounded temporary Git repository reproduced an optional index-refresh write
exceeding the unchanged 16 KiB child file-size cap: a 19,232-byte index caused
SIGXFSZ. Readonly `git --no-optional-locks` source queries preserve the index
bytes, accept unchanged committed contents and still expose dirty contents.
The original hosted failing command was not recorded, so this remains a
supported mechanism, not a proven exact hosted diagnosis. Closed command-stage
and numeric client return-code evidence now distinguish future failures without
publishing raw output. Two new tests first failed; all three new regressions
then passed. Focused/repository checks total 70 passed and one hosted-PG skip;
runner strict mypy and touched Ruff checks pass. No resource/deadline increase,
original-run retry or maximum trial. Corrected hosted evidence remains pending.
