# Pure once-only Actions guard contract

Local preparation only, before implementation; no API fetch, dispatch or fixture
execution. Planned consumer is the dedicated measurement job immediately before
setup, never a prior-job artifact. Pure validation is not authentication or a lock.

Frozen repository: IzignaMx/open-cycling-workshop, numeric ID1327018760; path
`.github/workflows/quote-ownership-measurement.yml`; ref `refs/heads/main`;
authorization ID is proposal SHA256
`1951f853a6e6cb1f57d0f66501726cfa370c33e9dd167b9f9a118aae463b8971`.
No authorization/path rotation. Trusted pins have exactly workflow_id (positive
exact integer), source_sha and tree_sha (40 lowercase hex). Workflow ID is frozen
independently after registration. Final source/tree are externally reviewed dispatch
values corroborated with API, not self-embedded hashes or proof of review. A guard
cannot prove its own source was reviewed; the authorized release coordinator controls
exact-head CI and dispatch.

Pure API: `validate_guard(context, pins, current_run, workflow, commit, main_ref, history_pages)`.
Context has exactly repository, ref, sha, workflow_ref, workflow_sha, event_name,
run_id, run_number, run_attempt, authorization_id. Numeric context fields are exact
positive ints (adapter explicitly normalizes real Actions environment strings).
Context matches all fixed pins; manual event workflow_dispatch and ordinals1/1.

Each response envelope has exactly url, status, content_type, link, body. URL is
exact expected api.github.com endpoint, status200, application/json, empty link,
body exact UTF8 bytes <=65536. No redirects/filters. Duplicate JSON keys at every
depth, nonfinite values, invalid UTF8 and nonobject roots refuse. Fixed error only:
`ownership_guard_refused`; no echo/context. Actual API extra fields allowed, required
identity fields exact. Future fetch adapter must bound before allocation and reject
failed/truncated responses; no fetch/token implementation belongs to this slice.

Endpoints: actions/runs/{run_id}, actions/workflows/{workflow_id},
git/commits/{source_sha}, git/ref/heads/main, actions/workflows/{workflow_id}/runs?per_page=100&page=1,
all under the fixed repository. Run fields: exact id/workflow_id/ordinals1/1,
eventmanual, head_branch=main, head_sha, path, status=in_progress, conclusion=null;
repository and head_repository id/full_name both fixed. Workflow id/path active;
commit sha/tree.sha exact. Current main ref must target the same exact commit. Current and history records must satisfy same identity.

History is exactly one complete unfiltered page: total_count exact integer1,
workflow_runs exactly one matching current run, no Link. Any extra/duplicate page,
record, total>1, filter, pagination, missing/unknown response refuses. A second run
already makes the grant ineligible; there is no reason to paginate it into approval.
One-page cap and64KiB per response give finite data-only parsing bounds.

Success returns closed binding: schema1, fixed authorization/repository/path/ref,
commit/tree, workflow_id/run_id as decimal strings, ordinals as int1. It is not a
reusable permit or durable spend ledger. First dispatch is spent on failed/unknown
guard/setup; no retry or workflow/auth recreation. History deletion by an admin is
outside immutable guarantees and requires stop/review. Same-job placement, actual
context provenance, manual-only workflow and publicAPI contents:read adapter remain
separate review gates. No new token permission. Tests use synthetic data only.
