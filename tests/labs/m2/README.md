# M2 synthetic laboratory — local functional increment only

This test-only package is not a production integration or a qualified M2 runtime.
The authority/application work exercises local ASGI/SQLite functional behavior;
that cannot prove PostgreSQL lock linearization, TLS, network isolation or process
resource enforcement. No normal application flag enables this laboratory.

## Prepared hosted harness (not yet executed)

The `runtime_*` modules and `scripts/ci/m2_lab_*.py` are authored for a future
explicitly approved isolated run. Importing or running the local test suite does
not launch them. Do not invoke their runtime entrypoints or publish the workflow
under preparation-only authority: PR publication would trigger execution.

See [prepared topology, bounds and remaining consent](../../../docs/10-spec-development/2026-11-02-m2-hosted-preparation.md).
Tests use fake commands/public file fixtures, pure parsers and approved memory
credentials; PostgreSQL/TLS/OS enforcement remains unqualified. The original
preflight below still refuses live execution rather than silently selecting an
unconfined fallback.

## Read-only execution preflight

From the repository root:

```sh
.venv/bin/python tests/labs/m2/preflight.py
.venv/bin/python -m pytest tests/labs/m2/test_preflight.py -q
```

The first command always exits **2 (blocked)** and emits only fixed, secret-free
status identifiers. It observes `docker`/`psql` executable presence and Linux
`CLOCK_BOOTTIME` API availability. It does not execute those tools, read a DSN or
credentials, contact any endpoint, launch a server/container, create a secret or
create/delete laboratory resources. API availability is not proof of clock
integrity. Executable presence is not proof of tool version, daemon access or
runtime policy enforcement. Supplied `EnvironmentFacts` are test observations,
not attestations. Even all-positive facts cannot authorize execution.

At implementation time this workspace has neither Docker nor psql. Exact local
observations and behavioral test results are recorded under `artifacts/m2-lab/`.
No process/CA/credential-file/database/volume cleanup is claimed for resources
this probe never created. Its tests use no production imports.

## Required evidence still missing

A later explicitly reviewed capable harness must establish, rather than accept
caller booleans for:

- Actual PostgreSQL18 transactions and concurrent authorization/revocation locks;
  a freshly owned synthetic database, never an operator-supplied general DSN.
- Separate non-root connector, verified run-local TLS hostname/certificate,
  enforced private egress and forbidden host/Core/Docker-socket mounts.
- Enforced CPU, memory, PIDs, temporary-volume, concurrency, transport byte/time,
  backlog and run-request limits specified in the accepted design.
- Suspend-inclusive deadlines and clock integrity; non-extendable15-minute run,
  termination/reaping and bounded5-second graceful shutdown.
- Verified disposal receipts individually covering credential files, CA keys,
  database/audit, connector store/volumes, network and processes, including crash
  paths. Failed cleanup remains failure, not an erasure claim.

There is intentionally no success/admission path in this preflight. Tests passing
mean the blocker inventory fails closed, **not** that these runtime gates passed.
Do not run an unconstrained substitute server or weaken isolation to bypass it.
Publication/deployment and production access remain outside this increment.

## Disposable one-shot functional reader

`connector.py` accepts only an explicitly injected in-process `TestClient`, an
existing fixture `Credential` and the trusted harness `MachineScope` obtained via
`authority.read`. It accepts no URL, DSN, path, environment credential or default
network client. The scope binding is fixture-supplied, **not a remote attestation**.
Only the closed five-field DTO is projected to an owned memory SQLite database,
partitioned by that exact nonsecret scope/run/generation. No credential is stored.
The one-shot reader allows at most four pages of50 items and64KiB per response,
refuses redirects, cycles and malformed DTOs, and has no retry/refresh/stale-data
accessor. A failed run purges partial results and stops; successful rows are only
returned by that current fetch. `close()` verifies zero rows before closing the
owned connection; `disposal_verified` is true only after both succeed. A cleanup
failure yields a fixed error and `cleanup_failed`; `closed` then means retired,
not proved disposed, and row counts refuse to attest zero. This is memory-state
disposal, not secure erasure or crash
teardown proof. Bytes already returned to a caller cannot be recalled.

`test_connector.py` uses actual local ASGI authentication/authority for successful
scoped reads and revoked denial. Explicitly labelled scripted responses test only
protocol rejection, pagination/resource caps and overlapping admission. Neither
these tests nor the reader qualify separate-process operation, TLS, enforced
network policy or a16MiB temporary volume. All execution preflight gates remain
blocked. Run the focused functional suite with:

```sh
.venv/bin/python -m pytest tests/labs/m2/test_connector.py -q
```
