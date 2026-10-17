# Fixed source-only Ruff repair proposal · 2026-10-17

Status: prepared for exact independent source review; unexecuted and unpublished.
This is a `repair_proposal_only` controller. Even six passing phases and final
Ruff exits 0 qualify only this bounded proposal, never the full static/contracts
batch, application behavior, PostgreSQL, capacity or activation.

## Preserved failing evidence and target

[Static run 39044828140](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39044828140)
ran commit `dff067af840b8e83d87d17ae6fa36cfd10e75653`, tree
`c3ba32738c5996badcf575bc47dfac9b9499fb4f`. Repository-contract verification
passed; Ruff check failed. Format, mypy, mounted OpenAPI and generated-client
checks were unrun. The closed diagnostic contained 146 unique supported records,
12 retained and 134 omitted, from 15,754 captured bytes; seven unparsed lines
were discarded. This does not establish that every actual finding was parsed.
The independent review accepted the failure evidence, actual containment,
cancellation and both final absence receipts. The failed run is preserved.

The new controller tree is distinct from the failed tree being repaired.
The new workflow checks out depth 2, requires HEAD's first
parent to be the exact failed commit and its tree to match, then archives only
the 19 literal target paths plus `ruff.toml` from that commit. Those 20 files
(363,424 bytes) are additional image inputs at `/opt/quote-static-repair-input`;
no copies are committed to the repository. The image's source label still binds
the current controller tree. Frozen SHA-256 values and sizes bind every target
file before copying. The final proposed patch applies only to the failed tree,
never to this changed controller tree without a separate reviewed preparation.

## Fixed workload

`tests/operations/test_quote_static_repair.py` supplies exactly these six nodes:

1. `test_copy_frozen_sources`: verify and copy the 19 Python sources and exact
   Ruff configuration to one private `/tmp` subtree. Do not import those sources.
2. `test_record_safe_ruff_fixes`: `/app/.venv/bin/ruff check --config ruff.toml
   --no-cache --output-format concise --fix --no-unsafe-fixes` plus the 19 paths.
3. `test_record_ruff_formatting`: the same executable with `format --config
   ruff.toml --no-cache` plus the 19 paths; require exit 0.
4. `test_record_post_repair_lint`: `check --config ruff.toml --no-cache
   --output-format concise` plus the same paths; record the real exit status.
5. `test_record_post_repair_format`: `format --config ruff.toml --no-cache
   --check` plus those paths; record the real exit status.
6. `test_export_patch_then_require_clean_final_checks`: emit the bounded proposal,
   then require both final checks to have exited 0. Exit 1 remains a failure.

The exact 19 paths, before hashes and finite diagnostic rule IDs are fixed in
`scripts/ci/quote_static_repair.py`; the workflow spells out that same archive
selection. They are the previous static gate's paths: six production files,
seven service tests and six controller/test files. No unsafe fixes, suppressions,
config relaxation, dependency changes or dynamic path selectors are requested.

Safe-fix exit 1 may represent residual findings and is retained as such. Delaying
the last two assertions permits exporting a reviewable still-red proposal;
`--maxfail=1` still stops on any operational error. Launch errors, timeouts,
output caps, unexpected exit codes, format-write failure and failed cleanup
cannot become successful proposals. They may prevent proposal export entirely.
Each of four tools has a 3-second ceiling; the unchanged shared 20-second
workload deadline is authoritative over all six phases and cleanup.

## Bounds and readback

The existing guard, cgroup checks, cancellation canary, private network,
read-only root, 64 MiB tmpfs, worker 1 CPU/512 MiB/64 PIDs and unused database
1 CPU/768 MiB/128 PIDs remain in place. No application DB protocol executes.
The original guard's image/build/client spool remains capped at 16 KiB.

Ruff needs to rewrite existing sources as large as 62,247 bytes, so its file-write
ceiling is 128 KiB per file, separately from its unchanged 16 KiB captured-output
cap. The fixed runner uses a nonblocking pipe, selectors and reads of at most
4,096 bytes; it never uses an unbounded communicate buffer or reader thread.
Its deadline is checked even after direct-child exit if a descendant holds the
pipe. Timeout/cap/error kills the process group and bounds direct reap to one
second; any kill/reap failure fails the phase. The outer container stop remains
the whole-descendant safety boundary. Copied source totals are capped at 512 KiB.

The receipt contains exact target IDs, all 19 before/after hashes and after sizes,
all four actual statuses, bounded numeric path/line/enumerated-rule diagnostics,
and a source-only unified patch. Unknown messages are discarded and only counts
remain. Up to 512 supported unique records per tool can be retained; completeness
is asserted only when the reported remaining count matches and no unsupported
path/rule line exists. The 16 KiB tool cap is never increased or retried.

Transport is one canonical JSON envelope: zlib <=10 KiB, total envelope plus
marker <=14 KiB, expanded canonical JSON <=256 KiB and UTF-8 patch <=192 KiB.
The actual patch/compression size is unknown until the contained run; exceeding
any limit fails without a retry or larger limit. No claim that these estimates
are observed sizes is made. The decoder rejects duplicate keys, NaN, noncanonical
JSON/base64, malformed hashes/indices, decompression overflow, missing EOF,
trailing/concatenated streams, duplicate paths and invalid unified hunk counts.
Only the fixed 19 ordered `a/` and `b/` headers are accepted. An empty diff is
accepted only with all 19 hashes and sizes unchanged, retaining residual findings.

Success uses one additional fixed `cat` within the guard's existing five-second
final-readback deadline. A final-check failure emits the same envelope before
the mandatory assertion; the host reads it only from the existing capped spool
after verified container stop and client reap. That path also requires the
original closed numeric failure marker to prove six completed phases and one
failed final call. The old failure status and numeric marker remain intact.

The normalized report explicitly says `repair_proposal_only`. The host writes
`artifacts/quote-static-repair-proposal.patch` only after bounded decoding; it
never applies or executes the patch. The receipt's after hashes are a bounded
worker claim requiring independent patch reconstruction/review before applying
to the failed tree. No patch means no proposed repair to apply. The optional
patch artifact accompanies the existing evidence and independent absence result.

## Review and remaining gates

The new receipt-negative test source covers canonical/duplicate/nonfinite JSON,
zlib trailing/concatenated/truncated/over-cap data, fixed paths/hashes, duplicate
diagnostics, hunk counts and final-status mismatch. These tests are unrun and
are not added to this six-phase workload. Source review is not runtime evidence.
No local candidate import, compilation, collection, test, static tool, build or
container run occurred while preparing this controller.

After exact controller review, a separately authorized contained run may produce
a proposal. Independently inspect the exact patch and reconstruct its hashes
before applying it to a fresh candidate from the failed tree. Only then prepare
a separate static/contracts qualification. The later four static tools remain
unrun; mounted OpenAPI does not qualify the unmounted quote service and generated
TypeScript freshness is not TypeScript compilation. Prior consumed workflows,
product/schema 0012, locks, fixtures and contracts remain byte-identical here.
Schema 0013, PostgreSQL application protocols and broader release gates stay open.
