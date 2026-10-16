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

## Corrected micro closure and single-record feasibility gate

[Corrected run 38890620234](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38890620234)
passed on merge `d26eb5de3437d0e3989d86fc358cbd1bdf3d1111`, tree
`55d64d47d3b4f7263432be89d56311bcd189ff15`, equal to reviewed correction
head `4501687b27c4dbcd911947599f188f51655c496e`. Independent artifact review
verified actual limits/privileges/network, three-generation cancellation canary,
three-command PostgreSQL microfixture, fresh load/retry and independent cleanup.
Total 5.768 seconds; bootstrap-inclusive micro 3.992 seconds; combined
canary/worker/database CPU 5.341425 seconds. Artifact 12041079916 ZIP SHA-256
`eed20561e9b8b2c4b069dc1c96894dffe82244c1bfa404cb5d32085558264874`.
This qualifies the tiny contained probe only. Original failed evidence is retained.

One separately recorded fixed feasibility fixture now uses the SAME 120-second
host/20-second workload deadlines, resource caps and fresh cancellation canary.
Original tiny baseline remains a separate run/artifact. Distinct owner manifests,
cidfiles and evidence paths prevent confusion; independent cleanup attempts both
fixed manifests even if one fails. No sweep, history builder, correction command
or maximum-history mode is added.

Reviewed input: 80 labor charges (60 minutes, 10,000 minor units/hour),
10 discounts (50 minor units each), 10 taxes (1,000 basis points each), each
adjustment targeting the first 50 charges: 100 lines and 1,000 edges. Raw and
normalized descriptions are 500 ASCII codepoints/bytes, evidence note 2,000,
source reference 200. These are fixed schema fields, not extra JSON padding.
Maximum UTF-8 lengths are not simultaneously claimed: 100 descriptions of
2,000 bytes alone exceed the 128 KiB request cap. No automatic downscaling.

One create and one initial full approval use existing request decoders; all
80 approved IDs derive from the locked revision, not a request selection.
Expected subtotal 800,000, discount 500, tax 499,500 and total 1,299,000.
Measure actual raw request bytes, joined canonical revision/decision bytes and
the two-record list without duplicate inner proof. Fresh reconstruction/retry
must retain two receipts/outboxes without added effects. Only closed metrics
are uploaded. Exact byte results remain pending hosted execution; no local
large-record/domain/PG construction was run. Seven small schema regressions
first failed, then passed; supervisor mocks cover both fixed modes.

A single-record result cannot prove valid 32/128 history. Correction-record
sizes/composition need later reviewed evidence. Accepted ADR section 7 permits
only ONE initial online decision after up to 32 pre-consent revisions, then
refuses edits/decisions; richer repository/restored histories are separate.
Ordinary API preliminary p50 <150 ms/p95 <500 ms/p99 <1 s come from phase-6 QA
section 25 and require representative nominal-load/hardware measurements.
Single hosted samples are not percentile or physical-device proof. Maximum
capacity/restore/atomicity, organization contention and activation remain open.

### First fixed-record result and bounded diagnostics

[Run 38892696736](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38892696736)
checked merge `3cc7c8911afdb8990247392a02d1e63c5dc0c6a5`, reviewed tree
`fca6f3e4f636b82166d0c344715b22b6793a3003`. Tiny baseline passed; the fixed
record failed `micro_failed` after 9.093 seconds, setup 2.033 seconds. Its actual
cgroup/privilege/network checks and cancellation canary passed; cleanup verified
absent and independent cleanup passed. Artifact 12042338200 ZIP SHA-256
`02a3246cac3826bdea1e527889eb48146c051614be1cf81a9962e6a3891df741`.
No inner phase, canonical byte totals or final resource snapshot was retained,
so this does not establish an invalid shape, capacity limit or exact root cause.
The recipe and all limits are unchanged; no blind rerun or parameter search.

Fixed-record-only checkpoints now retain an allowlisted phase, normalized failure
category and reached numeric byte counts, never raw exceptions/SQL/proofs.
The runner retains numeric pytest exit and last sampled resources, and attempts
closed checkpoint/final resource readback only within the ORIGINAL 20-second
workload deadline. An exhausted deadline yields unavailable evidence, not extra
time; cleanup still runs. Checkpoint writes are included in the measured work,
so later timings are instrumented diagnostic samples, not equivalent performance
claims. Seven diagnostic-schema tests first failed; guarded failure/expired-time
mocks cover capture without extending deadlines. No local recipe/PG execution.
