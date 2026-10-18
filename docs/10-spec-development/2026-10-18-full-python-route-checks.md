# Full-Python route: finite mock and static preparation

Status: 214 cases passed; static verification failed at Ruff with four later
commands unrun. The minimal style correction and static-only verification are
prepared but unrun. Ordinary CI, the full Python suite and activation remain
pending.

## Recorded result and narrow correction

[Run 39091798151](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39091798151)
executed once on commit `3695dfd896bb8e22a07fbd8671a77d3e1f37df8e`, tree
`2e353018c02e29e44069b2388b4a079bfcba3c98`. Its complete 214-case group passed
with zero failures, errors or skips. The static job passed repository
verification, then Ruff reported SIM105 in `quote_capacity_micro.py` and SIM300
in `verify_v01.py`. Formatting, production types, OpenAPI and generated-client
checks were unrun. Across 220 planned checks, retain 215 passes, one failed
command and four unrun commands; the consumed run remains failed.
Independent evidence review verified all 52 source pins, four locked inputs,
both cancellation canaries, bounded worker stop/client reap and primary plus
independent cleanup. The 214-case workload took 1.461891052 seconds; its final
pre-termination peak was 58,183,680 bytes. The failed static job has no successful
workload duration or final worker counters, so neither is inferred.

The correction changes only the reported source expressions: use
`contextlib.suppress(ProofFailure, OSError, ValueError)` around the existing
best-effort reconciliation, and put `Path("/app")` on the left of its equality
check. The permanent unverified-stop failure and all other control behavior
remain unchanged. Product, tests, locks and the consumed workflow are unchanged.
The 214-case evidence remains bound to its original source; it is not rerun or
relabeled as execution of the corrected source.

Use the existing `static6` selection once on the new exact
`codex/quote-full-python-style-checks` branch/workflow, first run/attempt only.
The six commands share the existing 20-second limit, one CPU and 512 MiB.
Refresh the two corrected source pins and add only the new workflow pin, giving
53 source pins and four locked inputs. Static XML/receipts remain capped at
16 KiB, workload output at 32 KiB, command output at 16 KiB and the failure
marker at 24 KiB. Image preparation, canary, cancellation and independent
cleanup are unchanged. The correction does not launch ordinary CI or the
900-second full-suite route. Its static result remains pending.

## Historical scope and source for run 39091798151

The following selection and resource details describe the consumed packet;
pre-run uncertainty statements do not override the recorded result above.

Before qualifying the new full-Python CI route, run exactly two serialized
20-second workloads through the existing contained verification mechanism:

| Group | Complete selection | Checks |
| --- | --- | ---: |
| `aggregate_mocks214` | Helper module 99, verifier module 108, seven directly affected CI/repository guards | 214 |
| `static6` | Repository, Ruff lint, Ruff format, production types, OpenAPI and generated client | 6 |

The first group contains 77 complete functions: 129 new mocked cases and 85
preserved cases. Both helper/verifier modules retain all parameter rows. The
seven guards cover backend/frontend/contract steps, manual dispatch and locks,
direct browser artifact ordering, API-client behavior, normative tool usage,
the browser database healthcheck and qualification artifacts. The literal
source/class/function/count/suffix map is in `scripts/ci/quote_integrity_checks.py`.
No selected test body is weakened or replaced by a wrapper test.

The five aggregate-route files and three corrected quote-test adapters are
preserved byte-for-byte. Product code, migrations, platform tests, apps, packages
and locks match the functional source at
[`b353c4b4`](https://github.com/IzignaMx/open-cycling-workshop/commit/b353c4b4d364ebfbcd1dc98134017c8bc6aae609).
Each future result must bind its actual qualification commit/tree, image,
52 source pins, four locked inputs and the intended clean-source snapshot.
Qualification-only workflows and helpers remain outside the clean integration
change.

The static wrapper owns the same fixed path/diagnostic constants that previously
lived in the experimental helper, so the clean helper need not regain those
controls. The two verifier paths extend the existing Ruff scope from 49 to 51
paths. The six commands and their `(2, 3, 3, 12, 6, 2)`-second subtimeouts remain
subordinate to their one shared 20-second workload.

## Resource and execution boundary

Use the existing Python 3.13.14 / uv 0.11.15 locked image with Git. Each worker
retains one CPU, 512 MiB, no extra swap, 64 PIDs, a read-only root/source,
unprivileged user, no capabilities, no-new-privileges and network-none. Its
64-MiB temporary filesystem remains noexec. Do not add Node, PostgreSQL clients,
a database or a browser to this finite stage.

The new full-supervisor and database/browser boundaries are mocked. Preserved
tests deliberately run small real subprocesses: Python version/exit probes,
a 17,000-character output-overflow probe, a two-second sleep cancelled by a
0.05-second timeout, a shell probe over tiny fixture files, and a temporary Git
repository with 240 small files. Inner waits remain subordinate to the external
20-second whole-worker cutoff. No scratch-created executable is required.

Finite protocol fixtures include one 8,192-node synthetic in-memory receipt,
a 4-MiB negative JSON file and just over 1 MiB of diagnostic bytes. They create
no application history. Host client output limits must not become worker file
size limits. Scratch, memory or timing exhaustion fails the attempt; source
review does not prove those allocations fit.

Leave the full-suite plugin inactive for this selection. The real cancellation
canary, bounded stop/reap, exact owned-resource reconciliation and independent
absence proof remain required. The two business budgets total 40 seconds;
preparation, setup and cleanup retain their separate existing bounds.

## Fixed output accounting

The successful 214-case XML inventory is conservatively bounded at **41,156
bytes**. Its complete closed report is bounded at **42,365 bytes**, including
52 source pins, four locks, source identity and an explicit envelope reserve.
Only this group's XML, fixed reader and receipt receive a strict **65,536-byte**
ceiling. Ordinary control-query and mock-output ceilings remain 16 KiB; static
output remains 32 KiB, command output 16 KiB and its failure marker 24 KiB.

The existing serial reader temporarily uses the larger ceiling only for the
one fixed XML read, restoring 16 KiB in `finally` before parsing, resource probes
or cleanup. Exact source/class/function counts, full matrices, unique observed
IDs, bounded suffixes and zero failures/errors/skips remain mandatory. Exit zero
alone is insufficient. Missing, truncated, oversized or partial evidence fails;
unrun checks are not passes. The successful XML bound does not promise that a
failure traceback fits its unchanged output spool.

## Prior evidence and remaining gates

[Run 39082181517](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082181517)
passed the 66 corrected functional cases, six mocks, repository and lint before
a formatter failure. Preserve that failure and its unrun tail.
[Run 39082876503](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082876503)
then passed the 12-check format closure in 14.579792505 seconds with independently
verified identity and cleanup. Its retained layout-only changes are reused in
the qualification controls. Neither run executes the new aggregate route.

The two-workload result and its static-only correction are recorded above.
Pinned Prettier for the changed ordinary CI workflow, the new Node/PG-client
image build, and the full collection remain pending. The eventual full suite
must preserve all six restore cases, the ordinary 100-line and 26-revision
specimens, and exactly the 58 intentional skip identities; missing dependency
skips must fail. Dedicated capacity recipes, the documented all-history
pre-reopen validator and production activation remain separate obligations.

The consumed packet used the first push run/attempt on
`codex/quote-full-python-mock-static`. Its matrix contains only the two groups
above. It does not trigger the ordinary 900-second CI route, open a PR, or
establish full-suite or capacity qualification.
