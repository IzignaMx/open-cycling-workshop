# Bounded branding images and durable private assets

Status: source and focused Linux tests implemented; container/image-build,
ARM64, physical-device and integrated recovery qualification remain separate.
This record covers synthetic image fixtures only. No real image, account,
installation, deployment, bootstrap or permission adoption was performed.
It implements Foundation ADR-014 and Phase 3 requirements 10/11/18 (tenant
isolation, upload validation, dependency evidence), within the shared-workshop
branding increment's finite scope.

## Decoder contract and resource boundary

`branding/images.py` accepts strict canonical Base64 containing at most 262,144
PNG bytes. Before creating a child it checks dimensions 1–512 per side, PNG
signature/framing/CRCs, chunk ordering, terminal IEND, at most 1,024 chunks and
8 KiB aggregate non-IDAT payload. The only admitted input chunks are IHDR,
PLTE, tRNS, IDAT, IEND, sRGB, gAMA and cHRM with their prescribed bounded
lengths. APNG, compressed metadata, unknown chunks and appended data are refused.

A fresh isolated-mode Python interpreter does exact bounded zlib scanline/EOF
checks, including Adam7 pass sizes, then Pillow's complete PNG decode. It never
uses header inspection as proof of decoding. Raw pixels are copied to a new
RGB/RGBA image and encoded as an 8-bit, non-interlaced, metadata-free PNG with
only IHDR/contiguous IDAT/IEND. Output dimensions, framing and byte ceiling are
rechecked. Metadata, original names and input diagnostics are not retained.
`inspect_canonical_png` verifies the strict emitted framing contract; it does
not run native decoding. Stored immutable bytes are bound to their SHA256.

Linux limits are set before importing Pillow: 128 MiB address space (not a
claim of 128 MiB RSS), two CPU seconds, 256 KiB output-file size, no core dump
and 32 open descriptors. The parent enforces a two-second wall deadline,
SIGKILLs/reaps a timed-out child, and releases the slot only after cleanup.
A nonblocking process-local lock permits one active decoder per API worker;
there is no waiting decode queue. Busy/unavailable are separate safe errors.
The child receives no application environment/secrets or database descriptors.
This is resource isolation, not a claim of a new OS security sandbox against
native code execution; the existing unprivileged hardened container remains
necessary. Non-Linux decoding fails closed.

Local Compose starts one Uvicorn worker, so the decoder ceiling is one child.
If an operator changes API worker/process/replica count, total child concurrency
and memory must be budgeted as that count times these limits and qualified
again; a per-worker lock is not a global deployment quota.

## Filesystem integrity and retention

`BrandingAssetStore` derives each private namespace from SHA256 of the exact
validated organization ID. It supports legacy non-UUID IDs without treating
identity text as a filesystem path. Keys are only `digest-prefix/digest`.
Construction and reads do not create directories. No path/key is an HTTP field.

The compatible `FilesystemBlobStorage` API now uses descriptor-relative,
no-follow directory/file operations. Owned directories must not be writable
by other users; unsafe ancestors and symlinks are rejected. Root-owned sticky
ancestors such as `/tmp` are permitted for owned private children. Files are
regular, owned and non-writable by others. The trust boundary still includes
same-UID processes and privileged host administrators. Supported durable
storage requires POSIX directory descriptors, hard links and directory fsync;
unsupported storage fails rather than weakening publication.

Publication uses an exclusive same-directory 0600 temporary file, full write,
file fsync, atomic no-replace hard link, temporary unlink and directory fsync.
New directories' parents are fsynced. Existing content is verified by bounded
size/digest/content comparison before successful deduplication. No referenced
file is overwritten. A failure after link may leave a complete unreferenced
blob but cannot return success without directory durability. Reads use fstat
before allocation and a bounded limit-plus-one read, then size/digest/framing
validation. Corrupt, missing, oversized or unsafe files fail explicitly.

Old blobs and crash-orphaned files are retained. This increment has no online
GC and no automatic deletion on replacement/removal. Capacity planning must
include every distinct canonical logo (up to 256 KiB each), directories,
filesystem allocation overhead, retained generations and rare crash temporaries.
Monitor the installation's actual volume capacity; it has no implicit quota.
Disk/permission failures must leave the SQL save uncommitted/unconfirmed and
never silently substitute a missing logo for a deliberate removal.

## Runtime ownership

API root: `/var/lib/ocwp/branding-assets`; local/default setting remains
`./var/branding-assets`, overridden by `OCWP_BRANDING_ASSET_ROOT`. Both local and
development API Compose services have a dedicated `branding_assets` volume.
The API image prepares its mount directory as 0700 UID/GID 10001. Docker's fresh
volume initialization uses that directory metadata. Local startup also runs
`branding-assets-init` as the same non-root user, without secrets or network,
to check existing private ownership and fsync writable storage. It never fixes
an old volume with chmod/chown or broadens host permissions. API startup depends
on that check. A bad old volume needs explicit operator diagnosis.

Worker and edge have no asset mount. Ordinary operations gets the asset volume
read-only. The explicit `branding-restore` profile runs `operations-restore`
with that volume writable at `/restore-branding-assets`, only in a fresh isolated
Compose project. The recovery CLI must reject populated SQL/assets and require
its explicit empty-target confirmation. The isolated API later sees the same
volume at its ordinary path. Backup input is read-only in the restore service.
Read-only roots, non-root identities, capability drops and no-new-privileges
remain in place. Docker is absent in this executor, so source checks and native
POSIX tests are not evidence of named-volume copy-up/runtime ownership or image
construction on either architecture. The integrated runtime workflow must
verify these before deployment.

## Pinned dependency and current advisory evidence

As checked on 2026-10-14, upstream's latest stable release is
[Pillow 12.3.0, released 2026-07-01](https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html).
Its security fixes include multiple format-specific memory/decompression issues.
Only PNG decoding and bounded RGB/RGBA PNG encoding are used here. PDF, EPS,
JPEG2000, fonts, external viewers, ImageMath and CMS transforms are not input
paths. This restriction supplements the maintained release; it does not waive
updates. [Upstream's security policy](https://github.com/python-pillow/Pillow/security)
calls out native decoder risk and image/resource isolation.

The manifest pins `Pillow==12.3.0`. uv 0.11.15 generated the lock from the official
PyPI registry. All 42 pre-existing registry package records/hashes remained
byte-for-byte equal as parsed; Pillow is the sole added registry record.
[Official release metadata](https://pypi.org/pypi/pillow/12.3.0/json) reports zero
vulnerabilities for this version when checked. Relevant SHA256 values:

- sdist: `3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce`
- CPython 3.13 manylinux x86_64 wheel: `0847a763afefb695bc912d7c131e7e0632d4edc1d8698f58ddabec8e46b8b6d3`
- CPython 3.13 manylinux aarch64 wheel: `f7401aebd7f581d7f83a439d87d474999317ee099218e5ad25d125290990ba65`

The ARM64 wheel's presence/hash is provenance evidence, not execution evidence.
Pillow's wheel also includes its upstream SBOM; the project-graph audit below
is not a separate audit of every bundled native library or container layer.

An isolated branding virtual environment was frozen-synced from the project
lock; existing/shared dependency environments were not modified. pip-audit
2.9.0 audited the fully hashed locked runtime+development export with no ignore
or exception: 43 registry records exported, 41 active Linux/Python 3.13 packages
audited, zero known vulnerabilities, zero skipped dependencies. The two inactive
Windows markers are colorama 0.4.6 and tzdata 2026.3. This is time-bounded advisory
evidence, not a promise of no unknown vulnerabilities or a Windows audit.

Reproduce with writable isolated tool/cache paths:

```sh
uv export --all-packages --group dev --locked --no-emit-workspace --no-header \
  --format requirements-txt --output-file artifacts/branding-assets/python-requirements.txt
pip-audit --disable-pip --no-deps --require-hashes \
  -r artifacts/branding-assets/python-requirements.txt \
  -f json -o artifacts/branding-assets/pip-audit.json
```

## Executed evidence and remaining gates

Tests first observed RED: missing image implementation, corrupt existing blob
wrongly accepted, bounded-read API absent, and absent runtime volume/ownership
setup. Subsequent focused cases exercise real subprocess decoding, timeout
kill/reap, a 150 MiB allocation refused under the actual 128 MiB address-space
limit, one active decoder with 31 immediate busy responses, metadata removal,
invalid scanlines/CRCs/APNG/deflate tails, canonical-output expansion, palette
and Adam7 decoding, tenant namespaces, 32 concurrent same-content publications,
symlink/FIFO/unsafe-permission refusal, sparse 10 GiB corrupt-file preallocation
refusal, disk failures and actual SIGKILL before/after immutable publication.
The process-death tests prove complete-or-absent bytes after process death;
they do not simulate a physical disk/power failure.

A separate 30-iteration synthetic 512×512 RGBA sample on this Linux x86_64
executor/Python 3.13.5 measured median 0.120 s, maximum 0.127 s and maximum child
RSS 25,784 KiB. These measurements do not establish hostile worst-case latency,
container limits, ARM64 performance or physical Raspberry qualification.
Generated logs/audit/metadata/sample JSON are under the ignored
`artifacts/branding-assets/` directory. The final focused decoder/storage/runtime-source suite passed 82 tests.
Touched-source Ruff and strict mypy pass.
Full integrated SQL/browser/recovery tests, independent review, hosted images,
named-volume ownership and supported architecture/device gates are owned by the
parent increment and remain open until separately executed.
