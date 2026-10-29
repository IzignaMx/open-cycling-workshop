# Actions adapter and manual workflow: local design for review

Preparation only; no dispatch, API fetch from the harness, image build or H/S run.
Pure guard source932af9c2 is already independently accepted. This addition wires
its actual planned consumer, not a new grant or consumption ledger. Role fixture
clarification is explicitly authorized for the disposable fixture only. Runtime
consumer and initializer implementation remain separately reviewed components.
This design was recorded before adapter/workflow implementation.

## Files and interfaces

- `scripts/ci/quote_ownership_actions_adapter.py`: bounded public GET adapter and
  CLI `--phase prebuild|setup --evidence PATH`. Reviewed expected source/tree and
  numeric workflow ID are fixed workflow inputs mapped through environment, never
  interpolated into shell source. No caller-selected URL/token/repository/path.
- `tests/operations/test_quote_ownership_actions_adapter.py`: mocked transport,
  clocks, environment, file outputs and workflow source-contract tests; no actual
  HTTP/process/DB/image invocation.
- `.github/workflows/quote-ownership-measurement.yml`: manual-only single55minjob,
  contents:read only, fixed concurrency group with cancel-in-progress:false.
  No Pages/OIDC/environment/secrets or additional permissions. No automatic trigger.
- Existing guard remains pure. Additional public repository and quiet-queue
  validation belongs to adapter, reusing the same bounded response parser.

Coordinator independently reviews final SHA/tree and registered workflow numeric
ID before dispatch. Input values cannot prove their own review. A workflow cannot
embed its own final source hash/tree. Fixed path/auth ID/repository ID are code
constants; no rotation/recreation to obtain another first run.

## Environment/context and API reads

Require real Actions environment (`GITHUB_ACTIONS=true`, GitHub public server/API
URLs), fixed repository/ID/ref, job identity from the dedicated workflow, normalized
positive decimal context IDs/ordinals and actual workflow_ref/workflow_sha. Assert
checked-out source/tree against reviewed inputs before fetching (workflow git
readback, not a caller-written pseudo context). Actual context values are passed
from Actions/environment rather than workflow-dispatch inputs.

Each phase fetches eleven exact endpoints with no retry:

1. Repository metadata: numericID1327018760, full_name fixed, public/notprivate,
   notarchived/notdisabled, defaultbranchmain.
2. Current run, workflow metadata, git commit, current main ref, one complete
   unfiltered dedicated-workflow history page (existing pure guard rules).
3. Five separate complete repository-wide active-state snapshots: in_progress,
   queued, requested, waiting, pending; per_page100/page1 with no other filters.
   in_progress must contain only this exact current run; others must contain zero.
   Any total/count/Link ambiguity, additional run or missing current run refuses.

Official REST docs permit unauthenticated public reads and define these five
nonterminal status filters. No Authorization header, GITHUB_TOKEN, PAT, netrc,
credential helper, environment proxy or redirected origin. TLS verification stays
on. Exact api.github.com HTTPS endpoints only; reject redirect instead of following.
Request fixed API version/Accept/User-Agent. Reject duplicate security/framing
headers (Content-Type/Length/Encoding/Transfer-Encoding/Link/Location); do not flatten
ambiguous headers into a dictionary. Response must be200, JSON media type,
no Content-Encoding except identity, bounded Content-Length when present, <=64KiB
actual bytes read before JSON decoding; duplicate keys/nonfinite/invalid UTF8 refuse.
No raw response/error text is logged. No caching or saved fixture response inputs.

Use one monotonic **45s total phase deadline**, initial connection/socket timeout at most5s clipped to remaining time,
and bounded chunk reads with deadline checks. Socket timeout alone is not an
absolute full-response/DNS bound; the external watchdog remains mandatory. These are
new guard-only fail-closed ceilings for review, not production/harness budgets.
DNS/native calls may not obey Python socket timeouts: workflow additionally wraps
adapter in external `timeout`45s with TERM then5s KILL. No subsequent setup/build
runs unless adapter exits0. The setup-phase guard is INSIDE the original65s setup
window: trusted workflow mints an absolute host-monotonic deadline before invoking
it and passes the unchanged deadline to controller. Its phase45s cap is clipped
to remaining setup time; an expired deadline refuses, never restarts. Initial
preimage guard is separate explicitly reported preimage overhead only. The wrapper establishes an outer failure gate, not
proof of graceful network cleanup. No retries if rate limited or metadata lags.
Five quiet snapshots are not an atomic global reservation; the release coordinator holds publication
queue before dispatch through terminal cleanup. Race/administrative history changes
remain explicit limitations, not a claim of an immutable Actions consumption lock.

## Evidence and failure semantics

CLI writes a <=16KiB phase-specific closed `unknown_spent` receipt before network
reads, exclusively creating a fresh output path. Anchor every directory component with
O_DIRECTORY|O_NOFOLLOW; create and rename relative to retained dirfds, recheck
requested-root identity and the pending record identity before success. Refuse
preexisting/symlink paths and root replacement; fixed repository evidence only.
The always-step fallback uses the same anchored helper, never a path-only writer.
On validated completion atomically replace with passed guard binding; on any failure
retain/refine only fixed refusal code and phase, never input/error text. Process
termination leaves unknown_spent. If CLI never starts, an always-run evidence step
creates a fixed missing_guard_unknown_spent record; absence is never passing.
Prebuild and setup receipts have distinct paths and cannot substitute for each other.
The first dispatch is spent even if initial guard or image preparation fails.
No attempt rerun, ID/path rotation or workflow recreation is permitted.

## Workflow sequence and existing resource constraints

1. Checkout actual github.sha, persist-credentials:false; source/tree readback and
   clean-worktree check; initial guard prebuild. Fail before any image build on refusal.
2. Locked full-Python image preparation from existing CI exact Dockerfile/build
   logic, within existing12min step/650s preparation budget, build590s/pull60s
   clipped to original preparation deadline and bounded command outputs. No larger
   images/resource policy or generalized supervisor. The worker image records source
   tree. Add only the reviewed source-bound derivative PG18.4 initializer: COPY exact
   existing role initializer and explicitly nonsecret fixed synthetic password fixture,
   using standard entrypoint/bootstrap postgres/dbpostgres to create ordinary ocwp.
   Select exactly one validated official postgres RepoDigest, inspect that exact
   reference back to the same configuration ID and Linux/amd64 platform, and use
   the manifest reference in FROM (never raw configuration ID). Record manifest
   reference plus base/derived configuration IDs; no host bind/new tmpfs or grants.
   PG pull and derived build share the existing60s PG preparation subwindow,
   clipped to the SAME original650s preparation deadline; insufficient time fails.
3. In ONE shell step: mint setup65s deadline FIRST, run fresh setup guard, then fixed
   measurement supervisor invocation with reviewed guard binding and image/source IDs.
   No intervening job/artifact or cached approval. Controller receives the SAME
   absolute host-monotonic setup deadline; guard time is already consumed. It may
   have insufficient time and must fail, not reset. The206s postimage envelope is
   unchanged, never256s. Canary15/other5/setup65/measurement26/cleanup55/finalizer60
   remain unchanged. Existing outer1020s and job55min remain ceilings, not retries.
4. Independent finalizer `if: always()` uses exact source/owned manifest and never
   starts H/S. If no fixture was created, report not_started/absence through its
   reviewed schema rather than fabricate successful measurement.
5. `if: always()` upload bounded guard/measurement/finalizer evidence; fixed failure
   fallback on missing receipt. No continue-on-error for guard/build/measurement.

Draft worker-confirmed CLI uses `--supervise|--finalize --worker-image --pg-image
--commit --guard-evidence --owned --evidence`. Enforce fixed paths:
RUNNER_TEMP/quote-ownership-owned.json, artifacts/quote-ownership/receipt.json and
phase-specific guard paths; never arbitrary overwrite destinations. Freeze exact
argv only after independent review; no speculative call is committed. No copy of the full-Python supervisor or
full-suite receipt. Workflow registration/source qualification precede the single
authorized maintainer-controlled dispatch. Ordinary CI tests inspect text/mocks, never invoke this job.

## TDD and review gates

Before implementation, the release coordinator and independent reviewer accept
this schema, timing and wiring choice. Tests first fail for redirects/proxy/token/header reuse, oversized/
truncated body, rate limits, time exhaustion, invalid environment, repository or
quiet snapshots, refusal receipt retention, stale preexisting artifact, manual-only
workflow/permissions and same-step setup ordering. Stub-to-GREEN then minimal code;
prove unsafe variants fail with targeted sensitivity tests. Final static/schema/
workflow checks and independent review before publication. No actual API fetch,
image/process/DB fault run is authorized by tests or this design document.

## Local preparation evidence (not venue execution)

Initial adapter stub:36 failing mocked cases, then GREEN. Workflow/shared-budget
prerequisites:6 failing cases before files/helpers existed, then GREEN. Independent
review reproduced a root-swap filesystem race; exact regression failed before the
dirfd correction and passes afterward, including a separate fallback-root-swap
case. Current52 adapter tests plus135 pure guard cases pass. Image metadata selection
adds19 pure/static cases after18 stub failures; no actual image build qualifies it. Strict mypy and
Ruff pass; shell blocks and inline Python have syntax-only checks. No real network,
Docker/image, child/observer or DB experiment was invoked. Executable workflow/
controller integration and final exact-source review remain gates.

## Closed artifact staging (review correction)

The uploader follows symbolic links, so a successful guard path check is not an
upload authorization. The always-run staging step copies only six closed JSON
records: both guard phases, receipt, cleanup, fixture preparation, and the existing
preparation metadata. Each source is opened relative to anchored no-follow directory
descriptors, must be a single-link regular file no larger than 16 KiB, and is checked
before and after reading. Total copied JSON is bounded to 96 KiB. Unknown entries,
symlinks, FIFOs, hardlinks, changed roots, invalid closed schemas or provenance fail
closed. The known preparation text is checked but never read or uploaded.

Receipt identities come from trusted workflow context/image outputs, never the
receipt itself. Cleanup's receipt digest must match the exact copied receipt bytes;
early cleanup with no identity must still match the expected source/run/attempt.
A passed receipt requires a separately verified-absent cleanup record with matching
identity and a non-null exact receipt digest. A missing, unknown or contradictory
cleanup record refuses the whole bundle, including any prematurely passed receipt.
Fixture file hashes are compared to the fixed checked-out source paths. A fresh
exclusive random directory under trusted RUNNER_TEMP receives only validated JSON
and a closed staging summary. Unsafe source yields only a fixed refusal summary,
not copied input or an acceptance receipt; the staging step remains failed. Unsafe
destination yields no upload directory. The workflow uploads only that generated
directory and does not use an evidence-tree glob. This does not defend against a
fully compromised same-UID runner replacing the trusted stage after it is created.
