# PostgreSQL settings-result correction

## Preserved failed evidence

[Run 39053071575](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39053071575)
on `d79eeed8dd9afbc493162b1c85769dcae526625e`, tree
`42061a3ad0fa3692e491d500d1c166005617bc7b`, collected six cases. Two DTO
cases passed; the first PostgreSQL create/decide/replay call failed after setup.
Three later PostgreSQL cases were unrun. The numeric diagnostic retained nine
reports, one failure, no collection or protocol errors, but no exception or
actual schema receipt. It does not establish the failing assertion or qualify
PostgreSQL business behavior. Artifact `12108915032` SHA-256:
`995aa10be7a3b1b81ff5c19d52aeec084b2fc4286c4deebf8cc5205698ff5480`.
Cancellation, client reap and both independent absence checks were verified.
The supervisor took 6.885 seconds including 2.096 seconds setup; these are not
successful workload latency measurements. Resource samples are last observed,
not proven final usage.

## Source-established correction

The PostgreSQL preflight converts `Result.tuples()` directly using `dict`.
In locked SQLAlchemy 2.0.52, `tuples()` returns the Result itself, which exposes
`keys()` but does not implement mapping subscription. Python selects mapping
conversion and raises TypeError instead of iterating the row pairs. The service
normalizes this as an integrity failure before its writer boundary. This is a
concrete source defect consistent with the failed case; the retained run does
not prove that exact exception occurred.

Use an explicit name/setting pair comprehension over the same three-setting
query. Preserve timeout validation, deadlines, authority, rollback and error
normalization. Prepare focused regression coverage for mapping-like iterable
results and malformed settings. No product code is executed on the authoring
host; those new regression tests remain unrun until a contained gate selects
them or the full integration suite runs.

## Corrected finite validation

Review the exact patch, then run the same two DTO and four PostgreSQL nodes once
on corrected source with the unchanged 20-second workload, one-CPU/512-MiB
worker and one-CPU/768-MiB owned PostgreSQL container. This is validation of a
specific product correction; preserve the original consumed workflow and run.
No schema 0013, routes or deployment are included.

Use the existing stopped/reaped output spool for bounded useful diagnostics:
pytest short traceback, explicitly no locals or captured logs, cleared process
environment and only synthetic fixtures. Retain at most 16 KiB of original
output as base64 with exact retained byte count and explicit truncation. The
existing 32-KiB service spool ceiling, cancellation and cleanup stay unchanged;
no extra subprocess, diagnostic catalog or resource extension is introduced.
A missing diagnostic never converts failure into success.

Require all six cases, 18 ordered phases, four distinct closed PostgreSQL 18.4 /
psycopg 3.3.4 / UTF-8 / revision-0012 identities, resource evidence and both
absence receipts. Retain the original response-failure callback-sentinel and
pre-writer deadline limitations. Concurrency, restore, capacity and activation
remain separate outstanding gates. Corrected-source execution is pending.
