# Fixed quote service static and contract preparation

## Status and source boundary

Prepared only, 2026-10-17 UTC. No candidate import, compilation, collection,
formatter, linter, typechecker, contract check, test, container, build or local
runtime was executed. No publication, PR or workflow launch is part of this
preparation. The authoring host's descendant/resource containment is unproved.
Git/byte/hash/source inspection is preparation evidence, never a runtime pass.

Base: independently accepted semantic commit
`a945039247decaec4f00fe3a04d125ba2d238208`, tree
`3f9b851f427c8d43746f7a3df5be308741ae6387`. A new worktree reconstructs those exact
tracked bytes and modes over local baseline
`f9849cbca62311d6fe090e5800986307a223cbd9`. The six production modules, all seven
quote tests, schema 0012, fixtures, existing configurations, contracts, dependency
locks and every consumed workflow stay byte-identical. No schema 0013,
effect-version admission amendment, service activation or product-semantic
change is combined here.

This is one fixed six-command gate using the existing contained service
mechanism. It is not a configurable runner, new containment layer, suite, matrix,
capacity fixture or retry. Only this new workflow is eligible:
`.github/workflows/quote-service-static-contracts.yml`, push branch
`codex/quote-service-static-contracts`, run 1, attempt 1. A fresh exact-source
review and separate publication decision remain required. A consumed/skipped
first run cannot be replaced implicitly.

## Prior exact evidence, retained independently

The original six cases passed in
[run 39041920516](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39041920516)
on commit `65e2e69df4c2ad134ff2256864e44256fc5d3b3a`, tree
`6c5d5d3f2af75f505262901f8099e89f5942f50f`. Artifact `12104491644`, ZIP SHA-256
`673a87843db6f3379472a000ddfc3f761568174f3f7afb935f8bf53c8580e78b`.

The distinct semantic six passed in
[run 39043072145](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39043072145),
job `117426303592`, on the base above. Artifact `12104344631`, ZIP SHA-256
`ce49d2c92a5c8d0d7b8824e55638d84be941145b37bd0b644cc9e0344b6ee424`.
Independent terminal evidence review accepted six exact tests and all 18 ordered
setup/call/teardown phases, zero failures/skips/collection/protocol/unhandled
errors, scoped source/image/resource receipts and both final absence receipts.
Setup was 2.538 seconds, workload including bootstrap 5.402 seconds, supervisor
8.360 seconds; worker peak 103,657,472 bytes, database peak 86,355,968 bytes and
combined workload CPU 5,990,638 microseconds. These are tiny-run observations,
not forecasts or capacity/latency claims.

That semantic gate closes the two fake-driver cases and selected SQLite
flag-off creation replay, actor/customer refusal, modeled acknowledgment loss
and post-append cooperative-expiry rollback. The strengthened clock assertion
executed. It does not establish real PostgreSQL timing or hard Python deadlines.
The successful runs do not exercise the actual failing-service marker path;
the real canary and synthetic collection regression supply their own separately
scoped cancellation/diagnostic evidence. No stop-before-nonblocking-reap ordering
is claimed. Initial failed run `39039629649` remains failed with its discarded
initiating exception unknown.

## Six exact nodes and commands

All nodes are in `tests/operations/test_quote_service_static_contracts.py`, in
this exact order. Each invokes its actual tool once and passes only on exit 0
without timeout/output-cap failure. Existing `--maxfail=1` remains: a first
failure leaves later nodes unrun, and reports must identify that narrower result.

1. `test_repository_contract`: `/app/.venv/bin/python scripts/ci/verify_repository.py`
2. `test_python_lint`: `/app/.venv/bin/ruff check --config ruff.toml --no-cache --output-format concise`, followed by the 19 paths below
3. `test_python_format`: `/app/.venv/bin/ruff format --config ruff.toml --check --no-cache`, followed by those same 19 paths
4. `test_production_types`: `/app/.venv/bin/mypy --config-file mypy.ini --cache-dir /dev/null --no-incremental --no-pretty --no-color-output --show-column-numbers --no-error-summary --show-error-codes`, followed by the first six paths below
5. `test_openapi_contract`: `/app/.venv/bin/python scripts/contracts/export_openapi.py --check`
6. `test_generated_client_contract`: `/app/.venv/bin/python scripts/contracts/generate_ts_client.py --check`

The lockfile already pins Ruff 0.16.5 and mypy 1.20.2. Existing strict mypy
configuration and ordinary import following are retained; there is no
`--follow-imports=skip`, ignored error, disabled lint rule or new dependency.
Caches are disabled rather than warmed outside the workload. The wrapper uses
fixed executable paths, no shell, a cleared child environment, one Ruff worker,
no inherited database/pytest settings and `/app` as its required working root.

Exact lint/format paths, first six also being the mypy roots:

- `services/platform/src/cycling_workshop/quotes/effects.py`
- `services/platform/src/cycling_workshop/quotes/reconstruction.py`
- `services/platform/src/cycling_workshop/quotes/repository.py`
- `services/platform/src/cycling_workshop/quotes/responses.py`
- `services/platform/src/cycling_workshop/quotes/service.py`
- `services/platform/src/cycling_workshop/sync/writes.py`
- `services/platform/tests/quotes/test_quote_application_service.py`
- `services/platform/tests/quotes/test_quote_atomic_effects.py`
- `services/platform/tests/quotes/test_quote_command_response.py`
- `services/platform/tests/quotes/test_quote_driver_budgets.py`
- `services/platform/tests/quotes/test_quote_reconstruction.py`
- `services/platform/tests/quotes/test_quote_result_codec_once.py`
- `services/platform/tests/quotes/test_quote_single_pass.py`
- `scripts/ci/quote_capacity_micro.py`
- `scripts/ci/quote_collection_regression.py`
- `scripts/ci/quote_guard_bootstrap.py`
- `tests/operations/test_quote_capacity_micro.py`
- `tests/operations/test_quote_service_collection.py`
- `tests/operations/test_quote_service_static_contracts.py`

The frozen historical guard oracle is explicitly excluded and preserved. The
six production roots total 95,459 bytes. The original 18 selected files totaled
344,327 bytes at the base; the exact final selection sizes/hashes are in the
review manifest. Mypy may read their transitive module/type dependency closure;
six roots are not a claim that only six files are parsed. No tests in these
linted files are executed merely because Ruff reads them.

## Actual contract scope

`verify_repository.py` checks its 14 required files, ten required directories
and AGPL license text. It does not run the broader repository test suite.
`export_openapi.py --check` imports the application, including its module-level
application construction, builds the fixed contract application and renders
OpenAPI. Source inspection shows no session factory, lifespan execution,
request dispatch or database call in this path; that expectation still needs
runtime evidence. It covers the existing mounted API. The new quote service
remains unmounted and its future exposed API is not qualified by this check.
`generate_ts_client.py --check` checks generated-file freshness from that saved
OpenAPI file. It is not TypeScript compilation or runtime client validation.

No SQLite file or quote operation is created by the selected commands. The
existing PostgreSQL container remains unused environment overhead; its legacy
receipt label still says `unused_postgresql_environment_overhead_sqlite_tests_only`.
For this source the actual scope is static/contracts, with zero selected SQLite
protocols and zero PostgreSQL application protocols. Preserve that distinction.

## Exact additional image inputs

The same archived-source image preparation remains, with explicit additional
`COPY` inputs. These 25 tracked files total **246,220 bytes** and have their own
review-manifest hashes. No untracked file, credential, host cache or arbitrary
workspace directory is added. The original build Dockerfile, lockfiles and
base image preparation are unchanged.

Root inputs: `ruff.toml`, `mypy.ini`, `LICENSE`, `README.md`, `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `SECURITY.md`, `GOVERNANCE.md`, `MAINTAINERS.md`,
`ARCHITECTURE.md`, `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json`,
`.python-version`, `.nvmrc`.

Contract inputs: `packages/api-client/openapi.json` and
`packages/api-client/src/generated.ts`.

Real directory sentinels: `apps/web/package.json`, `packages/ui/package.json`,
`packages/plugin-sdk/package.json`, `packages/branding/package.json`,
`infra/compose/docker-compose.dev.yml`, `fixtures/minimal/fixture.json`,
`fixtures/demo-workshop/fixture.json`, `fixtures/load/fixture.json`.

The existing image already carries `pyproject.toml`, `uv.lock`, platform sources,
all scripts and tests. Sentinel files establish real required directory
presence; no fixture loader, Compose command, frontend install or load specimen
executes. Final image provenance remains bound to the complete source tree.

## Closed failure diagnostics

The ordinary six-protocol acceptance and existing numeric service-failure marker
are unchanged. A failing tool can additionally emit one `OCWP_STATIC_FAILURE_V1`
marker, at most 4,096 bytes, outside pytest capture. No raw tool/pytest output is
printed, retained in an artifact or released from capture. The diagnostic has
only these closed fields:

- `schema=1`, fixed `tool` index 0 through 5 and actual `returncode` (null only
  when launch fails).
- `kind`: 1 nonzero normal exit, 2 local timeout, 3 output cap, 4 launch failure.
- `output_bytes` at most 16,384, `omitted` and `unparsed_lines` bounded counters.
- At most 12 unique records containing only an exact permitted repository `path`,
  `line` from 0 through 1,000,000 and an explicitly enumerated `rule`.

Ruff uses an explicit finite subset of known codes; unlisted codes remain
uncopied and count as unparsed lines. The 78 mypy codes were enumerated by
read-only text extraction from the installed matching 1.20.2 `errorcodes.py`;
no tool or candidate import was used to obtain them. Exact rule allowlists,
per-tool exact path allowlists and fixed contract/format/repository labels
prevent arbitrary bracketed messages from becoming diagnostic data. Unknown
paths/codes/messages, traceback lines and source text are discarded. This is a
bounded first-error aid, not a promise to retain every issue or its prose.

The parser rejects unknown/duplicate JSON keys, nonfinite values, booleans in
integer fields, unknown paths/rules, control characters, duplicate records,
oversize/truncated/multiple markers and noncanonical JSON. It also binds the
tool index to the existing numeric failure marker: exactly one failed call,
complete protocols for that first failed tool and all predecessors, no other
errors/skips, exit status 1. Missing or invalid diagnostics are unavailable and
never turn a failed tool into a pass.

The supervisor reads this only from its existing capped host-side spool after
verified whole-workload stop and client reaping, adjacent to existing numeric
failure parsing. It adds no Docker read, mount, endpoint or new cleanup phase.
Normal successful evidence remains exactly six successful complete protocols.
Marker/parser negative cases are prepared in the existing operations test
module for later ordinary contained CI; they are **unrun** and are not additional
selected nodes or a separate guard layer in this preparation.

## Unchanged containment, smaller tool ceilings and feasibility

- Worker: 1 CPU quota, 512 MiB RAM, zero swap, 64 PIDs, UID/GID 10001.
- Database overhead: separate 1 CPU quota, 768 MiB RAM, zero swap, 128 PIDs.
- Canary: worker limits; removed before the database/worker pair. The pair's
  simultaneous allocation remains two quotas and 1,280 MiB, not one aggregate CPU.
- Existing private cgroup, read-only rootfs, no capabilities/no-new-privileges,
  no Docker logging, isolated network, ownership/source/image checks, zero
  pressure requirements and 64-MiB `/tmp` tmpfs stay unchanged. Database data
  and socket tmpfs remain 256 MiB and 16 MiB.
- Setup: 30 seconds. Entire workload including pytest bootstrap, imports and
  teardown: **20 seconds**. Pair workload CPU: 40 seconds; pair lifetime: 60;
  canary: 10; aggregate including canary: 70. No resource increase or retry.
- Per-command time ceilings in order: **2, 3, 3, 12, 3, 2 seconds**. These sum to
  25 seconds but do not allocate 25 seconds: the shared outer 20-second deadline
  is authoritative, and later commands may remain unrun. Every tool's output
  tempfile has a 16-KiB `RLIMIT_FSIZE`, with only a 16-KiB read and no unbounded
  `communicate()` buffer. The output file resides in the existing tmpfs.
- Tool timeout sends SIGKILL to its process group and waits at most one second
  for the direct child. Any kill/reap failure is a failing protocol, never
  success. The existing whole-container guard owns all descendants, resource
  pressure, final cancellation and absence proof. Local subprocess handling is
  not a replacement containment mechanism.
- Existing final sampling (5 seconds), failure cancellation (5), cleanup (35),
  outer supervisor timeout/kill grace (120/30) and independent cleanup
  (55-second internal, one-minute step) are unchanged. Image preparation retains
  its existing bounded 300/300/60-second commands and 12-minute step.

Prior ordinary CI run `38978404344` took about 6.07 seconds for the full 113-file
mypy command and about 0.76 seconds for OpenAPI rendering. Those observations
make this finite trial plausible, but do not establish cold performance under
this worker's 512-MiB/one-CPU limits or qualify this source. A timeout, pressure,
cap, first lint/type finding or missing diagnostic stays a bounded failure;
there is no automatic rerun, larger allocation or weakened rule.

## Acceptance and remaining gates

Require exact independent source/manifests/selection/image-input review before
any publication. A successful later run must prove all six actual commands,
all 18 ordered phases, zero errors/skips, source/image/actual containment and
final resource evidence plus both final absence receipts. A failed run retains
its exact failure, closed diagnostics if available and observed/unrun scope;
partial success cannot be called complete static/contracts qualification.

Even success does not qualify broad Python/frontend static analysis, TypeScript
compilation, the new service's exposed contract, wider grants/enrollment,
APPROVE/REJECT, complete replay/association/cleanup behavior, versioned payloads
or schema reconciliation, PostgreSQL atomicity/concurrency/real driver timing,
hard service deadlines, HTTP/UI, capacity, restore, physical devices or
activation. No deployment or maximum workload is authorized by preparation.
