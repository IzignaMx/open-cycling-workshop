# Synthetic branding decoder smoke in the ARM64 image

Status: initial and diagnostic hosted image builds succeeded, but both qualifying
QEMU decoder attempts **failed** on their exact candidates below. A narrow worker
startup/import correction has native x86_64 source/test evidence and awaits new
exact-tree hosted execution. A separate standard hosted native ARM64 job is now
implemented with local control-flow tests; actual native ARM64 execution is still
pending publication and runner availability. This executor has no Docker. Physical
Raspberry, laptop/Docker Desktop and hostile worst-case qualification remain separate. Named-volume/recovery evidence belongs to its
own runtime artifact and does not change this ARM failure.

## Execution and artifact boundary

The existing Local runtime workflow retains the three `linux/arm64` image builds.
`web` and `operations` remain cache-only. `platform.local` is loaded with an
ephemeral exact-SHA tag into that runner's Docker store, with `push: false`; no
registry publication, paid runner, account or deployment is introduced.

The workflow inspects the loaded image ID and OS/architecture, then runs
`scripts/ci/branding_image_probe.py` through stdin, using `python -I -` in that
image. It does not mount the checkout over the installed application. It keeps
the image's default UID/GID 10001, read-only root, dropped capabilities,
no-new-privileges, init and the production-size 64 MiB noexec/nosuid `/tmp` tmpfs.
Network access is disabled and no application secrets/environment are supplied.
The probe checks actual UID/GID, effective capabilities, no-new-privileges,
`aarch64` process architecture and the Python executable's ARM64 ELF machine ID.
It refuses to import a decoder outside the image's installed `/app/.venv` tree.

One generated 2×2 RGBA PNG, including allowed `gAMA` and `sRGB` metadata, goes
through the actual installed `canonicalize_logo`. The probe observes the real
Popen call and forwards its arguments unchanged: same interpreter, isolated
mode, closed inherited descriptors, PATH-only child environment, file-backed
output and discarded diagnostics. One real successful child is required. It
checks canonical framing, metadata removal, dimensions, byte count and SHA256,
then verifies the exact four expected RGBA pixels with a fixed-output-size
standard-library check capped at 19 inflated bytes. It does not compare a
compression-library-specific fixed PNG digest or import Pillow into the parent.

Only the bounded probe report `artifacts/branding-arm64-emulated.json` is uploaded
by the evidence-upload step, under artifact name
`branding-arm64-emulated-${{ github.sha }}`. The closed report is under 4 KiB and
includes the exact checked-out commit, actual loaded image ID/platform, installed
worker source digest, Python/Pillow versions, process checks and canonical output
metadata. No PNG/base64, environment, credentials, decoder diagnostics or raw
exception text is printed or uploaded. Safe failure reports are uploaded too;
a container/build startup failure with no report remains a failed gate rather
than fabricated evidence.

## Limits and interpretation

The qualifying attempt checks the installed worker's unconditional pre-Pillow
limit declarations:
128 MiB address space, two CPU seconds, 256 KiB output, zero core bytes and 32
open descriptors. Its existing two-second parent wall deadline is unchanged.
This is explicitly `installed_worker_source_checked` evidence combined with a
real decoder invocation, **not** a child kernel-limit observation or RSS measure.
The real production timeout/kill/reap and memory-limit tests remain separate.

Every emulated-job report labels execution `qemu-emulated-linux-arm64` and records
`physical_device_qualified: false`. Its single elapsed interval is an emulated
smoke diagnostic, not a Raspberry timing, RSS or worst-case capacity benchmark.
QEMU may need address-space overhead incompatible with the unchanged 128 MiB
limit. A refusal or timeout fails this gate; there is no relaxed-limit retry,
native-host fallback or success reinterpretation. If this occurs, preserve the
safe failure and leave ARM runtime qualification open for a separately authorized
native supported runner/device test.

## Local evidence

TDD observed the missing probe import fail, then helper/mock checks pass. Further
RED/GREEN cases cover safe CLI failures and exact pixel preservation. Tests cover
ELF architecture, synthetic PNG framing, all five PNG scanline filters, wrong or
oversized pixels, fixed limit declarations/order, subprocess forwarding and
isolation, rejected checkout imports, bounded safe output, and a refusal without
retry. Full success orchestration is explicitly mocked; it proves report/control
structure, not Docker, QEMU, native ARM64 or actual installed-image execution.

The initial source scope passed 34 focused cases and 60 combined probe/runtime-
source cases. Ruff, formatting, strict mypy for the probe, repository contract
and extracted workflow shell syntax passed. Independent review reran all 34
focused cases and found no open source blocker; actual hosted execution remains
pending for the diagnostic additions.

Reproduce the local scope without modifying dependency environments:

```sh
.venv/bin/python -m pytest -q tests/operations/test_branding_image_probe.py
.venv/bin/python -m ruff check scripts/ci/branding_image_probe.py tests/operations/test_branding_image_probe.py
.venv/bin/python -m ruff format --check scripts/ci/branding_image_probe.py tests/operations/test_branding_image_probe.py
.venv/bin/python -m mypy scripts/ci/branding_image_probe.py
```

See the [decoder/storage contract](../03-security-privacy/2026-10-14-branding-image-storage.md)
and [local runtime qualification boundary](2026-10-14-local-runtime.md). Hosted
execution must be recorded against the final reviewed candidate before claiming
that this emulated-image check passed.

## Initial hosted failure and diagnostic-only follow-up

The initial run [38655208868](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38655208868)
checked merge `eb4a31b55af4ef1a698daf58762da41c01b8b78b`, exact tree
`416f0737d677b2c810af7be302facee03fe9340e`. The loaded image ID was
`sha256:a50284c7dc7cd0326e315b09c1847a4cf7842c9530b80971bdb00f9efd7d9bb8`.
[Artifact 11936163954](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38655208868/artifacts/11936163954)
has uploaded ZIP SHA256
`05f95beb0621706879400de48e959d4544bf4e598d94fa563b15812030cc2268`.
Its installed worker SHA256 is
`b5ca430ef94a6273e11314d2cccd7277c620a8bc62c4295e3411ea8378e7465c`, matching the
initial reviewed production source.

The report proves ARM64 image/process identity, UID/GID 10001, hardened runtime,
Pillow 12.3.0 and source-declared limits. Its outcome was
`decoder_unavailable_under_emulation` after 2.009593 seconds. This is consistent
with the two-second deadline, but that original report did not record whether
`communicate` timed out, the child's exit/signal or CPU time. It cannot distinguish
interpreter/module/Pillow startup from decoding or a resource-limit failure. It
does not establish cold-start causation or a native ARM portability defect.

The source-only diagnostic extension preserves the original qualifying call,
arguments, resource limits, failure and nonzero exit. Its witness now records
spawn wall time, an actually observed `TimeoutExpired`, final exit/reap status
and child user/system CPU deltas, including on failure. These original-attempt
observations are primary; CPU is the emulated child process's CPU consumption,
not a native Raspberry measure.

Only after `DecoderUnavailable`, exactly one separate diagnostic child executes
the unchanged installed worker with the same two-second parent wall deadline
and the worker's unchanged CPU/address-space/output/descriptor limits. It has
a single additional private marker descriptor, discarded stderr and private
file-backed image output. Its line tracer emits only fixed Python/worker entry,
limit, Pillow-import, decode and encode landmarks with numeric wall/CPU values.
There are at most 11 markers. Reading is capped at 2,049 bytes to detect a 2,048-
byte overflow; more than 12 lines also discards the marker stream. Unknown,
duplicate, nonnumeric, non-ASCII or out-of-range lines are discarded, never
copied into evidence. Timeout and unexpected failures kill and reap the child;
a kill/exit race still waits for the child. Raw image output is never reported.

The diagnostic is explicitly `instrumented_second_child_not_original_attempt`.
Bootstrap imports, tracing overhead and second-attempt warm-cache ordering can
move the observed bottleneck. A missing marker means only `not_observed`, never
proof that the original child was stuck at startup. The last marker is an observed
boundary, not a causal verdict about the next operation. For example,
`limits_start` without `limits_applied` can mean a limit call failed, a later
limit call failed, or marker emission failed under the applied limits. Even a
completed diagnostic
cannot make the original qualification pass or change exit 1. No production
optimization, limit change, workflow retry or native fallback is introduced.
Further causal conclusions require the new exact-tree hosted evidence and review.

The added RED/GREEN cases exercise failure retention, original timeout versus
exit evidence, marker byte/count/input bounds, single-child spawning, unchanged
arguments/limits, CPU fields, kill/reap on timeout/unexpected error/exit race,
and complete omission of unrecognized or image output. Local helper/mock results
are separate from actual emulated diagnostic execution.

The diagnostic source scope passes 53 focused helper/mock cases. An independent
reviewer also executed one native Linux diagnostic against the unchanged
checkout worker with the project virtual environment: all 11 markers through
`worker_complete`, exit 0 and reaped. This validates local marker plumbing only;
it is not the installed `/app` image, QEMU, ARM64 or physical-device evidence.
The full failed-report regression includes all 11 markers and verifies the
original failure, commit and image ID remain intact under the 4 KiB ceiling.

## Corrected diagnostic result and bounded worker startup correction

The diagnostic run checked merge `b537a33bd3fc963ec0c559d771ef878b48ead422`, tree
`bd0fa97aacca042f9ebb473f6622de4782f9b146`, with the same image/worker digest as
the first run. Its qualifying attempt observed a parent wall timeout after
2.010173 seconds, spawn time 0.006577 seconds, child user CPU 1.968709 seconds
and system CPU 0.027995 seconds, with the child killed/reaped at exit -9. The
supporting instrumented child observed `python_ready` at 0.450244 seconds but
never observed `worker_entry`; it too timed out and was reaped. This demonstrates
a CPU-active deadline failure. The second child's phase still does not locate
the original attempt or distinguish every possible emulator/resource effect.

Read-only source/import investigation found that standalone execution loaded
API-side imports, created an unused API lock and built the public DTO before
entering the worker and applying its existing resource limits. The bounded
correction keeps the same file path and isolated-Python command, but initializes
API-only imports, `CanonicalLogo` and `_DECODER_SLOT` only for a normal module
import (`__name__ != '__main__'`). Normal API imports retain the same frozen
public dataclass and one shared process-local lock. The private `_Png` parsed
record becomes an immutable typed `NamedTuple`, retaining the field order,
constructor and attribute-read behavior used by its current callers; it avoids
the dataclasses/inspect dependency chain in the standalone child. Pillow already
needs typing, so this cost is included rather than omitted from the comparison.

AST comparison against the pre-change source proves `_inspect`,
`inspect_canonical_png`, `_validate_scanlines`, `canonicalize_logo` and
`_worker_main` are unchanged. Framing/CRC/chunk/dimension rules, native full
decode/re-encode, output validation, subprocess/environment/descriptor contract,
nonblocking concurrency, cleanup and all limits are therefore preserved. The
parent deadline still starts before Popen. No parser is copied, no interpreter
`-S` shortcut is used, and no warming, retry, process pool or increased budget is
introduced.

Native Linux x86_64 source-only observations, with the fixed synthetic 2×2 input:

- Exact unchanged worker invocation before the change: exit 0, 0.064247 seconds
  wall, 0.063410 seconds child CPU; after: exit 0, 0.064263 seconds wall, 0.050746
  seconds child CPU. These are individual observations, not a benchmark or a
  measured wall-latency improvement.
- Separate `-X importtime` invocations against the same source file report
  112 → 48 import records before the worker's resource import, and 155 → 122
  records for the complete decode/encode graph. These include interpreter/site
  startup and import attempts; they are not counts of third-party dependencies.
- Summed pre-resource import self-time was 28.442 → 10.288 ms in those profiled
  observations. The new early typing import is included, at 1.816 ms cumulative;
  it adds no module to the complete graph because Pillow imports typing anyway.
  Some deferred modules, including tempfile/subprocess, are imported later by
  Pillow. They are not claimed to have disappeared from the whole decoder.
- Eight synthetic inputs preserve identical canonical SHA256, byte count and
  dimensions before/after: color-metadata RGBA, RGB, grayscale, grayscale-alpha,
  palette/transparency, 16-bit grayscale, one-pixel Adam7 and 512×512 RGBA. No
  image bytes are stored in this evidence record.

RED/GREEN regressions prove a fresh isolated child reaches worker entry without
API-only globals/import roots, while normal imports preserve the frozen public
DTO/API and the shared lock. They also verify `_Png` field order/types/read values
and refusal of attribute assignment/addition. The existing actual-decode,
malformed-input, metadata/pixel, expansion, timeout kill/reap, 128 MiB allocation
refusal and concurrency tests continue to run; no elapsed threshold is added as
an optimization correctness gate.

This correction reduces the observed import graph. It does not prove where the
original emulated child stopped, predict a green QEMU run, establish native ARM
performance or close physical Raspberry qualification. Both prior failed
artifacts remain failures; only new exact-tree evidence can establish the next
qualifying outcome.

The startup correction passed 84 decoder/probe cases. The broader selected
branding/storage/recovery/source suite passed 246 cases with 28 explicit
PostgreSQL-environment skips and three dependency warnings; those skips are not
PostgreSQL evidence. Full platform strict mypy passed 99 source files; touched
Ruff/format, documentation formatting, repository contract and diff checks passed.
Independent review reran all 84 decoder/probe cases and verified unchanged ASTs
for the five functions and all six admission/resource constants. Local source
checks do not replace the still-required exact-tree QEMU run.

## Separate standard hosted native ARM64 qualification

The additional `arm64-native-decoder` job uses the literal standard hosted runner
`ubuntu-24.04-arm`. Its job-level guard requires both
`github.event.repository.private == false` and
`toJSON(github.event.repository.private) == 'false'`. The serialization check is
required because GitHub expressions loosely equate null and false: private,
missing/null, numeric zero, a string `"false"` and other nonboolean metadata must
all skip this job. There is no larger-runner/custom-label fallback, permission
expansion, external account, registry publication or paid-runner opt-in. Queueing
or unavailable capacity remains a pending gate rather than a reason to switch
targets. Hosted execution and its actual scheduling are not proven locally.

This is a separate qualification path. The existing QEMU matrix, defaults,
image-build cache settings, diagnostic second child and failure artifacts remain
unchanged. A native pass cannot change either historical QEMU failure or close
the current emulated gate. No physical Raspberry, device performance or supported
installation claim follows from a hosted native pass.

Before building or launching a container, the shell independently checks the
host `uname -m` equals `aarch64`, the host Python ELF machine equals 183,
`RUNNER_ARCH` equals `ARM64`, and the Docker daemon architecture is `aarch64` or
`arm64`. The guest does not infer these host facts from its own uname. They are
recorded as `workflow_validated_host_inputs`; the in-container process/ELF,
UID/GID, Python isolation, capabilities and no-new-privileges checks remain
separate evidence.

The job runs plain local `docker build --platform linux/arm64` with the same
`infra/docker/platform.local.Dockerfile` and exact checkout source. It adds no
build-push action, registry push, artifact, build-record or remote-cache upload.
The built image ID and platform are inspected, and the native container runs by
that immutable image ID rather than resolving its tag again. The installed worker
SHA256 must match the worker obtained directly from `git show` at the checked-out
commit in the host-side validation step; report commit
and image ID must match the checkout and inspected image exactly. Failed early
phases may omit facts not yet observed, but cannot satisfy a passing report.
The final source digest therefore binds a passing installed worker to this
checkout without mounting source over the installed application.

The native container keeps the same hardened settings and production decoder
invocation/limits described above. It performs one qualifying attempt, with no
second diagnostic child, retry, warm-up or relaxed budget. A native refusal is
`decoder_unavailable_on_native_arm64`, with original attempt timing/process
observations when available, and a nonzero exit. Native reports use the explicit
`native-linux-arm64` execution label and `native_elapsed_seconds`; every report
still sets `physical_device_qualified: false`. Elapsed time is a single synthetic
smoke observation, not a benchmark or worst-case capacity estimate.

The job has a 20-minute ceiling; its qualification step has 18 minutes. The build
has a 900-second TERM deadline plus five-second KILL escalation, container run
30 seconds plus five seconds, and targeted cleanup 10 seconds plus five seconds.
Cleanup names only this run/attempt's ephemeral container and removes its own
temporary report. The production decoder remains at two wall/CPU seconds and
128 MiB address space; outer orchestration limits do not enlarge those limits.

Container stdout is captured privately, and build/container diagnostics are
suppressed. A host-side validator reads at most 4,096 bytes and accepts only a
report strictly smaller than that bound. It rejects malformed/deep JSON,
duplicate keys, unknown fields, unexpected types, nonfinite/out-of-range numbers,
wrong source/image/host facts, mismatched status and process exit, or incomplete
passing evidence. A pass requires all schema fields, the matching source digest,
exact pixel/canonical-output evidence and one successfully exited, reaped child.
Missing or invalid process-exit evidence cannot be normalized into a valid
failed report. Any rejected/missing report becomes only a fixed safe failure
object; neither raw output nor exception text is used as a fallback. Only the
validated bounded JSON (or fixed bounded failure) reaches the job log/summary.
No image bytes, private files or separate native artifact are uploaded.

### Local source evidence and remaining hosted gate

The recovered first implementation passed 89 helper/mock tests. Additional
observed RED/GREEN cases covered duplicate root/nested keys, missing or invalid
process status and the cleanup KILL escalation. The expanded focused suite passes
112 cases. It pins the entire public-only guard and standard runner rather than
checking permissive substrings, and covers nonboolean/missing metadata,
source/image/host/schema/size/status refusals and native failure without a second
child. Ten hermetic shell scenarios execute the workflow script with synthetic
identity and Docker commands: host/ELF/runner/daemon mismatch, build/inspect
failure, raw/empty output, a valid failure and an exit/status disagreement. They
verify bounded sanitized output, preserved nonzero exit and cleanup of only the
named ephemeral container. These are shell/control-flow tests, not actual Docker
or ARM execution.

Tests use this worktree's isolated Python 3.13.5 virtual environment with Pillow
12.3.0; shared dependency trees are unchanged. Actual installed-image native
ARM64 evidence still requires publication, standard-runner scheduling and a new
exact-tree hosted run. Preserve that run's URL/job, checked commit, image ID and
worker SHA256 with its outcome before changing the qualification status.
