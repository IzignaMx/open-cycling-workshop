# Existing quote integration regressions

Status: selection design and exact implementation independently reviewed;
execution pending.

## Purpose and source

The private quote service, bounded effect reconstruction and migration 0013
have separate finite functional evidence. The next step checks their affected
existing callers, repository oracles, schema surrogates and installation gates.
It adds no product behavior or new acceptance matrix.

The preparation base is commit
`03e11cd8c0ea6e22955c748fc58abe00c90405b5`, tree
`f0ef88823094bc4e74bdfa8795e4d68597efb751`.
[Its static run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39078898414)
passed the six existing commands in 14.408 seconds. That result does not prove
the new selection or its combined workload.

One obsolete negative specimen in `test_cutover_cli.py` changes from revision
0013 to 0014. The production installation gate already supports 0010 through
0013; its positive matrix retains all four. This source-established test-data
correction has no observed failing-before result and changes no production gate.

## Fixed scope

The proposed selection contains 337 checks in 23 serialized workloads:
325 existing functional cases, six existing selection mocks and six static
commands. Complete selected functions and their nondialect parameter matrices
are preserved. PostgreSQL and SQLite observations remain distinct.

- SQLite repository, reconstruction, single-pass oracle, result-codec and
  history-byte regressions; six selected read functions.
- Selected schema constraints, retention and replacement behavior; SQLite
  metadata/prepared-writer surrogates and adjacent migration-head checks.
- Existing outbox, REST feed, order-sync and selected generic sync regressions.
- The full cutover CLI module, including the corrected unsupported revision.
- Eleven existing PostgreSQL repository race/savepoint cases, 26 schema cases
  and two adjacent migration-head cases.
- Six existing selection mocks, followed by repository, Ruff, formatting,
  production typing, OpenAPI and generated-client checks in one final workload.

The 100-line large proof/result specimen and the 26-revision pagination
specimen are excluded from this finite stage. Unlisted tests remain unqualified
by this selection. No broad test glob, caller-defined selector or consumed
experiment is used.

## Resource and evidence boundaries

Every workload retains its own 20-second deadline, one CPU and 512 MiB worker
limit. PostgreSQL jobs retain the existing isolated PostgreSQL 18.4 service with
one CPU and 768 MiB. The summed business allocation is 460 seconds; groups do
not borrow unused time. Preparation, canary, cleanup and queue costs are
separate. Each job retains its existing 20-minute ceiling, so 460 seconds is
not an end-to-end completion estimate.

The complete 37-case reconstruction function and larger migration groups may
not fit. Existing timings support a bounded attempt, not a promise. The final
combined group adds six mock functions to the measured 14.408-second static
baseline. A deadline, truncated report, missing identity, failed test or unrun
tail remains a failed qualification; no larger budget or automatic rerun follows.

The existing controller and fixed workflow enforce source/image/lock identity,
exact selection counts, bounded diagnostics, a real cancellation canary,
verified worker cancellation, client reap and independent owned-resource cleanup.
Failure diagnostics are read only after verified stop and reap.
Previously consumed workflows remain unchanged. PostgreSQL evidence requires
the actual dialect, driver/server versions, UTF8 encodings, revision 0013,
isolated schema and a closed independent probe for each selected case.

The older repository fixtures own `ocwp_access_*` schemas. Only that exact
source may use that prefix; other selected migration fixtures retain their
original schema boundary. Its final probe runs before the owning fixture tears
down. This final identity observation does not replace the selected test bodies'
intermediate migration, locking or rollback assertions.

## Acceptance and remaining work

The source review covered exact selectors, typed PostgreSQL parameter matrices,
fixture ownership, complete bounded reports, unchanged limits and the full
source diff. After execution, independently verify the exact commit/tree,
case and phase counts, failures/skips, resource receipts and cleanup before
recording any passed scope here.

This page currently records preparation only. No new run, artifact or passing
case is claimed. The final clean integration candidate still requires its own
source-equivalence review and aggregate integration gate.

Capacity and ordinary-operation latency, total Python deadline enforcement,
broader contention, complete pre-reopen history validation, HTTP/API/UI,
production activation and physical installation remain separate obligations.
The earlier failed capacity/profile experiments and unknown original restart
cause remain preserved in their existing evidence documents.
