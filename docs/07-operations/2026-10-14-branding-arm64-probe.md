# Synthetic branding decoder smoke in the ARM64 image

Status: source implemented and helper/mock tests executed; the actual image build
and QEMU container probe have **not** run in this executor, which has no Docker.
This does not close physical Raspberry, laptop/Docker Desktop, hostile worst-case,
named-volume ownership or integrated recovery qualification.

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

Only `artifacts/branding-arm64-emulated.json` is uploaded, under artifact name
`branding-arm64-emulated-${{ github.sha }}`. The closed report is under 4 KiB and
includes the exact checked-out commit, actual loaded image ID/platform, installed
worker source digest, Python/Pillow versions, process checks and canonical output
metadata. No PNG/base64, environment, credentials, decoder diagnostics or raw
exception text is printed or uploaded. Safe failure reports are uploaded too;
a container/build startup failure with no report remains a failed gate rather
than fabricated evidence.

## Limits and interpretation

The installed worker's unconditional pre-Pillow limit declarations are checked:
128 MiB address space, two CPU seconds, 256 KiB output, zero core bytes and 32
open descriptors. Its existing two-second parent wall deadline is unchanged.
This is explicitly `installed_worker_source_checked` evidence combined with a
real decoder invocation, **not** a child kernel-limit observation or RSS measure.
The real production timeout/kill/reap and memory-limit tests remain separate.

Every report labels execution `qemu-emulated-linux-arm64` and records
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

The final local scope passed 34 new focused cases and 60 combined probe/runtime-
source cases. Ruff, formatting, strict mypy for the probe, repository contract
and extracted workflow shell syntax passed. Independent review reran all 34
focused cases and found no open source blocker; actual hosted execution remains
pending.

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
that this newly authored emulated-image check passed.
