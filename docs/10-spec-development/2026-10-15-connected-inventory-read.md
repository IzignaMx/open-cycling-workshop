# Connected inventory visibility: bounded implementation plan

Status: implemented; independent source findings corrected; exact integrated hosted qualification pending, 2026-10-15. Base: actual main `22b32a9e29f5b9dca9d52c2e8d36ac1228047c54`, tree `d715e514f437e88fa4a5199c7f1a5eaa6e13c5ea` (merged PR40). Implementation must start in a fresh worktree from newly verified main. This record preserves the original acceptance matrix. The linked implementation ADR incorporates the mandatory independent-review corrections and takes precedence for exact contracts.

Implementation ADR: [bounded connected inventory read](../02-technical-architecture/2026-10-15-connected-inventory-read.md).

## 1. Outcome and boundary

A user with current `inventory.read` can open Inventory for one authorized workshop, page its existing product catalog, select a product, see its ledger-derived **available quantity**, and page its immutable movement history. All four personal themes, schemes, density, shared branding and existing operational/offline work continue to behave as before.

This completes only connected inventory visibility. Offline inventory snapshots, offline reads, writes/commands, uncertain-write recovery, product creation/editing, adjustments, reservations, releases, consumption controls, purchasing, pricing, alerts, barcode/variants, quote API/editor/decisions and inventory reconciliation remain unimplemented in this UI. Existing backend commands remain supported. Requirements for later offline inventory are retained, not removed. Quote identity/decision/partial-price ADR remains a separate pending proposal, with no quote code in this slice. No strict dependency on quotes was found for this catalog/stock/ledger read path.

Use existing SQL0011 and authenticated local schema7 unchanged. Do not consume SQL0012/local8, add an inventory IndexedDB store or queue, extend baseline-2/entity unions, change write protocol/catalog/grants, activate tenants, or reinterpret legacy17 wildcard authority.

## 2. Traceability and inherited facts

Normative sources, relative to repository root:

- `docs/01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md`: FR-INV-001 (existing basic product subset only), FR-INV-002 (per-location visibility), FR-INV-003/004 and BR-006 (immutable movements and derived stock), FR-IAM-004/008, SEC-002, NFR-004/007/010/014; ACC-002/003/004/005/007/008/009/010. FR-INV-001 in full and the inventory module remain open.
- `docs/04-ux-design/open-cycling-workshop-platform-phase-4-ux-ui-design-system-v0.1.md`: FL-09 first three stages only; SCR-040/041/042. Its compensating-adjustment stage is deferred.
- `docs/02-technical-architecture/2026-10-13-inventory-command-atomicity.md`: available = SUM(signed ledger quantities); RESERVE negative; RELEASE and CONSUME positive; CONSUME has atomic negative ADJUST companion; finalization is whole-reservation. The UI must preserve these conventions.
- `docs/superpowers/plans/2026-09-01-v0.2-increment-2-budgets-inventory.md`, `docs/10-spec-development/2026-10-14-local-workshop-mvp.md`, master loop and execution-state/manual: this is partial delivery, not completion of Increment2, offline requirements or MVP qualification.

Actual source anchors: `inventory/{router,schemas,repository,service,models}.py`, `identity/{dependencies,cutover,administration,roles}.py`, `app.py`; client `runtime/{account-access,controller}.ts`, `features/administration/{model,transport}.ts`, `features/branding/controller.ts`, `vite.config.ts` and `pwa-navigation-policy.mjs`.

Already available: GET product list, GET product stock, inventory.read, tenant/product indexes and append-only ledger. Missing: movement-history GET, inventory screen and transport. Identified read gaps, verified on the exact base: `services/platform/src/cycling_workshop/app.py:79–116` omits inventory from private no-store classification; `inventory/router.py:70–106` uses dependency-time authorization and DB reads without a transaction-owned after-wait actor refresh. `identity/dependencies.py:66–94` closes its separate auth session before those reads. Address those narrowly below; do not widen this into a global auth refactor.

PR40 inherited premerge evidence is closed (27/27 controls, 2,374 Python/14 skips, 728 frontend, direct63 + separate aggregate63 browser, kernel14, repeat20+9, reviewed185 originals; runtime/recovery/security/native ARM64 +3 builds). Parent owns fresh main postmerge verification. Its direct browser run currently has 62 expected passes and one flaky administration clock case (first attempt failed at a past `clock.pauseAt`, retry passed); a separate owner is fixing that test from fresh main. Do not claim postmerge-clean or modify that owner's files. Rebase/reconcile the future inventory worktree after this QA correction lands. Separate QEMU diagnostic remains failed/non-qualifying with cause unproven; physical Pi and full accessibility qualification remain open. Historical YAML status blocks are not global completion statements.

## 3. Proposed wire contract to freeze before parallel source work

### Existing reads: byte/shape compatible

1. `GET /api/v1/inventory/products?location_id=...&limit=...&offset=...` retains existing bare ProductResponse array, fields, bounds (limit1..200, offset0..2147483647), `(name,id)` ordering and status semantics. UI requests 50 rows, bounded previous/next pages; a full page may lead to an empty final page. Do not fetch the entire catalog or call stock for every row. Catalog offset paging is live, not a stable snapshot; explicit refresh resets to page1. No search control that misleadingly searches only the visible page.
2. `GET /api/v1/inventory/products/{product_id}/stock` retains StockResponse, including JSON integer `available_quantity`, and current scope/error semantics. Do not rename it to physical/on-hand stock, clamp negative values, round unsafe values, or sum only the loaded ledger page. Show quantity only for the selected product.

### One additive endpoint

`GET /api/v1/inventory/products/{product_id}/movements?limit=50&before=<opaque cursor>`

- Requires existing `inventory.read`; product/path identifiers retain existing length/NUL rules. limit is integer1..100, default50. On this new endpoint only, unknown or duplicate query parameters return422; the old catalog query behavior is unchanged.
- Response is exactly `{items: InventoryMovementReadResponse[], next_cursor: string|null}`. Each item has exactly `movement_id`, `product_id`, `organization_id`, `location_id`, `kind`, `quantity`, `occurred_at`. This explicit allowlist preserves signed quantities but excludes `actor_id`, `order_id`, `reference_movement_id`, `note`, user/customer details and any enrichment. These omitted fields must not appear even as null values. The existing write-only POST MovementResponse is unchanged. All returned rows must match the authenticated organization and selected product's location/product.
- Query explicit organization + location + product predicates. Order `(occurred_at DESC, movement_id DESC)`, strict lexicographic `< before`; fetch limit+1, return at most limit, next_cursor only when another row exists. Timestamp ties are resolved by immutable movement_id. This is a live history page, not a cross-request snapshot or complete reservation-state reconstruction.
- Cursor: version1, URL-safe canonical base64 without padding, at most2048 ASCII characters and decoded UTF-8 at most1024 bytes. Exact JSON fields: `version: 1`, `organization_id`, `location_id`, `product_id`, `before_occurred_at`, `before_movement_id`. Canonical encoding uses sorted keys, compact separators, UTF-8 and no unnecessary escaping; timestamp is UTC `YYYY-MM-DDTHH:mm:ss.ffffffZ`. IDs retain existing length1..36/NUL-free rules. Decoder rejects malformed/duplicate/unknown fields, noncanonical encoding, invalid/range-exceeding timestamps/IDs, and scope/product mismatches with generic422 `invalid_inventory_cursor`. The token is a position, never an authorization credential; unsigned is acceptable because all scope predicates and current authorization are independently enforced. Do not expose raw decoded errors. Pin exact bytes and canonical UTC cases in tests and the implementation ADR before clients are delegated.
- A cursor copied to another authorized product/workshop/tenant is rejected, never silently ignored. Foreign/nonexistent product handling remains consistent with existing scoped_product (foreign tenant404, same-tenant wrong location403); errors contain no foreign row data. Cursor validity never establishes that an entity exists or is authorized.
- Leave persisted historical rows/metadata unchanged; only the new read projection omits sensitive columns. Do not fabricate a CONSUME/ADJUST grouping or assume adjacent page rows are a whole transaction. The UI explains each signed delta, and a visible consumption row may have its physical-issue companion on another page.

### Authenticated read boundary and caching

All three inventory reads use one small read-only transaction helper: organization compatibility/incarnation lock → current actor lock/refresh → literal incoming/current grant intersection → scope/capability validation → query → final expiry check, with locks held until response materialization/transaction completion. Reuse existing `lock_compatibility`, incarnation checks, `effective_principal` semantics and token clock where sound; never call a writer admission primitive merely to obtain its lock if that imposes a write-protocol transition or issues write admission evidence. Use populate-existing refresh where required. No commit, audit mutation, ledger write or receipt is produced by GET.

Preserve valid legacy floor0 reads and valid floor1 reads without X-OCWP-Write-Protocol; fail existing quarantined/incompatible/stale-incarnation sessions as before. No activation or recovery flag. Show read-only authorization in a focused ADR with lock ordering and actual PostgreSQL revocation/expiry race tests. Read completion that serialized before revocation may succeed; a read waiting behind committed revocation must refuse. Do not claim revocation can retract bytes already delivered.

Extend private no-store classification to the exact inventory namespace, including validation/auth/internal-error responses. Do not intercept similarly prefixed unrelated paths. Client requests use cache:no-store and require no-store responses. Built PWA never caches inventory JSON and never serves HTML shell as an inventory API response; retain existing API navigation exclusion. Do not log bearer tokens, cursor payloads, notes or private response bodies.

## 4. Client ownership, numerical safety and UX

- Use the existing runtime account/session owner and an immutable request capture, never a second login or token-derived admission. Scope is one selected concrete workshop: bound-account location, or an already selected runtime workshop; organization-wide accounts may use the existing authorized location-directory path only with locations.read. Without an eligible selection, explain that a workshop must be selected. Do not require inventory users to acquire unrelated admin/order grants, infer a workshop from a product result, or offer an arbitrary tenant-ID entry.
- Capture current account, selected scope, runtime identity/generation and mount/request generation. Abort and clear inventory rows, selected product and cursors on account/scope/epoch/incarnation/lease-owner invalidation, logout, offline transition, route disposal or newer request. Guard stale success AND stale error after await, including A→B→A and noncooperative fetch. Use existing account invalidation/held semantics through a narrow generic facade if needed; do not call a branding-specific method as a new inventory authority mechanism.
- A missing/rejected permission clears protected data; 401 triggers the existing invalid-session path and 403 requires current authority verification. No automatic capability adoption. Legacy '*' authorizes inventory.read only through frozen17. inventory.write alone does not imply inventory.read. Existing user roles remain unchanged.
- Bounded strict transport validates Content-Type, no-store, JSON shape, actual body bytes ≤1MiB, page bounds, IDs/scope, timestamps, enums and cursor length/progress; receiver-bound fetch, finite deadline/abort, safe generic errors. Match current transport conventions rather than adding a generic client framework. Reject duplicate/mismatched movement rows and malformed ordering; retain at most one catalog page and one ledger page in volatile UI state.
- JSON quantities/versions must be safe integers before display or arithmetic. A stock aggregate outside JS safe range becomes explicit unavailable/unsupported-value state, never rounded or zero. Retain legacy JSON shape; decimal-string transport is a separately reviewed follow-on if full-range display is needed. Boundary tests cover ±(2^53−1), ±2^53, floats, booleans, strings and negative available stock.
- Catalog shows SKU/name/unit. Product detail shows Available quantity, a refresh action and read-time freshness. Ledger shows movement identifier, kind, signed delta with the selected product's unit, and timestamp. No notes, actor/account IDs, order/customer IDs or reservation reference IDs are delivered or rendered by this slice, even when the caller separately holds other read grants. No cross-module links or detail fetches. Treat product names/SKUs and all returned labels as plain text, never HTML. Later enriched history needs its own reviewed field-permission contract.
- Stock and ledger are independent reads: show separate loading/error/freshness states and state that refreshing one does not prove both represent the same instant. No equality assertion between stock and a partial ledger sum. Refresh starts ledger at newest and resets cursor. Older replaces the page; Newest returns to the first page, avoiding unbounded retained history.
- Provide loading, empty catalog, no movements, populated, denied, invalid session, network/server error, unsupported quantity and disconnected states. Disconnect clears connected inventory data and explains that inventory is unavailable offline while existing local workshop work remains preserved. Do not show stale inventory as authoritative or claim that browser online state proves server reachability.
- Route/entry and controls follow current shell patterns, with explicit readable connection status, keyboard focus restoration after paging, announced results/errors, non-color-only signs, touch targets, full words/reflow and horizontal-overflow prevention. Keep all four themes, dark/light schemes, compact/workshop density and shared logo/palette behavior; do not change personal preferences or branding algorithms.

## 5. Acceptance/test matrix (write failing tests first)

| ID      | Proof                 | Required cases and evidence                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| INV-R01 | API contract          | Old catalog/stock exact shapes and bounds unchanged; valid legacy floor0 and floor1 reads without write header; new ledger empty/one/exact-limit/limit+1/multiple pages, tie timestamps, both consume rows, negative stock; no duplicate/missing rows for a fixed fixture.                                                                                                                                                                                   |
| INV-R02 | Authority             | No token401; inventory.write-only403; inventory.read succeeds; legacy17 wildcard; scoped vs organization-wide principals; foreign tenant404, wrong location403; guessed product/cursor cannot reveal rows. No new grants/adoption.                                                                                                                                                                                                                           |
| INV-R03 | Real PostgreSQL race  | Read blocked behind revoke/deactivate/scope move/incarnation change/expiry refuses after fresh recheck. Conversely, read acquired first completes under consistent lock order before revocation. Bounded concurrent read/write exercise and no deadlock; SQLite tests do not count as this evidence.                                                                                                                                                         |
| INV-R04 | Pagination/limits     | Invalid/oversized/noncanonical/duplicate-field cursor; wrong version/scope/product; query duplicates/bounds; equal timestamps; inserts between pages documented live semantics; limit+1 bounded output and DB query; no full-ledger materialization. Existing indexes inspected; no migration unless measured evidence requires a separately reviewed change.                                                                                                |
| INV-R05 | Read-only/privacy     | Before/after ledger, products, grants, receipts, outbox, audit and protocol/incarnation values identical; GET no writer admission/activation. no-store on200/401/403/404/422/500; safe errors/logs; allowlist exactness with synthetic secrets in note and unrelated actor/order/reference columns; partial-permission inventory.read-only users receive no omitted key/value, and additional grants do not expand this response; API HTML fallback refused. |
| INV-R06 | Transport             | Strict body shape/size, safe integers, identifiers/scope/kind/time, duplicate rows/order, cursor progress, abort/deadline/non-JSON/missing no-store/401/403. Native fetch receiver binding. No token/request payload in snapshots or errors.                                                                                                                                                                                                                 |
| INV-R07 | Controller/lifecycle  | Stale success/error after workshop/account A→B→A, token refresh/revocation, logout, expiry, offline, takeover and unmount; no unauthorized request, no publication from obsolete generation, one-page memory bounds, retry only explicit GET refresh.                                                                                                                                                                                                        |
| INV-R08 | UI/accessibility      | Each substantive state, signed deltas/explanatory text, both consumption rows across page boundary, empty final catalog page, negative/unsafe stock, keyboard/paging focus, live announcements, long product name/SKU/reflow. Four themes and representative dark/light, density,320px,tablet/desktop,CSS200,forced colors. CSS zoom is not browser zoom/physical touch/screen-reader certification.                                                         |
| INV-R09 | Hosted real journey   | Disposable synthetic scoped users/products/ledger on actual API+PostgreSQL: catalog→stock→Older→Newest→refresh; permission denial and account/workshop switching; disconnect/reload clears inventory and preserves existing pending operational journal/delivery history; inventory read issues no POST/PATCH/DELETE. Assert states before original screenshots.                                                                                             |
| INV-R10 | Integrated regression | Required full Python/frontend/static/contracts/build/PWA/native browser/kernel/repeat/security/runtime/recovery/native ARM64+three-build gates on final exact source. Existing inventory command race/replay/atomicity suites stay green; baseline-2/SQL0011/local7 unchanged. QEMU is reported separately under accepted criterion. Review bounded unique screenshots, not copied artifacts.                                                                |

## 6. Work packages, review and handoff

1. Fresh-main reconciliation + failing contract/security tests; freeze exact cursor schema, query behavior, read barrier, error mapping and client capture interface in a small repository ADR. Ask for review before any deviation from this scope or version boundary.
2. Backend owner: additive read endpoint/query/schema, narrowly shared read guard and no-store coverage, unit/API/PostgreSQL tests. No command semantics changes.
3. Frontend owner (only after interface freeze): bounded transport/controller + read screen + navigation, tests and synthetic browser journeys. Distinct files can be delegated; coordinator owns runtime integration and avoids concurrent edits.
4. Independent exact-source review of backend authority/pagination and client lifecycle/permission/number handling, then integrated required suites and actual hosted evidence. Close findings before freeze/publication. Parent owns all remote publication/merge and final hosted orchestration.
5. Update CHANGELOG, module README, ADR, user-facing connected-only limitation and execution-state/manual with additive current increment entries. Preserve historical evidence/status, pending offline inventory/quote requirements and original journals. Record exact commit/tree, reviewed source hashes, environment paths, executed vs skipped/collected counts and unique screenshot hashes. No production-ready claim.

Stop at this read slice. A later write UI needs durable uncertain-command reconciliation; future quote acceptance needs reviewed identity/authorization/price/stock effects and offline protocol. Neither is implicitly authorized by this plan.

## 7. Implementation and evidence checkpoint

The interface review preceded frontend delegation. Modular DCO commits preserve
SQL0011/local7/baseline-2, old GET operations and response schemas, literal grants,
write commands, operational forms/journal, themes and shared branding. Local
functional tests use this checkout's source with a reused interpreter/dependency
store; no fresh frozen dependency installation is claimed.

Independent review found four frontend boundaries and all were reproduced before
correction: asynchronous durable-owner takeover, account revalidation A→B→A,
expired 10-second requests while timer callbacks are delayed, and metadata-directory
recovery after 403. Corrections check the actual owner around every request,
retain session generations, recheck raw wall/monotonic deadlines, and permit a
freshly verified bounded directory without a baseline. Final focused 105 checks,
80 runtime regressions and 7 independent adverse probes pass with zero skips.
A test fixture reused an incremental cursor during scheduled sync; it now advances
page/continuation/checkpoint IDs. No production observer defect was established.

Independent backend review passed 335 functional checks. It confirmed organization→
fresh actor lock order, narrow projection, matching binary predicate/order,
expiry/materialization boundary, no commit/admission and budget cleanup by source.
Actual 43-case PostgreSQL proof is locally blocked; SQLite does not qualify races,
2s/5s/8s database limits or measured 20,001/100,000-row query plans.

Actual Uvicorn privacy checks pass. Edge source/mocked proof reviews found and
corrected stale-success artifacts, unchecked cleanup and acceptance of access-only
logs. Both Caddy configs preserve only inventory query privacy, including encoded
paths and absolute-form targets. Actual Docker/Caddy execution is locally blocked.
CI runs `inventory_read_proof.py` and `inventory_edge_probe.py` fail closed, uploading
only safe measured JSON; incomplete/skipped/source-mismatched evidence cannot qualify.

Seventeen actual-browser scenarios are authored and collected, with strict typing,
finite isolated retry fixtures and no automatic credential-bearing traces/video.
Four-theme original captures include desktop/tablet/320px/CSS200/forced colors,
control-word geometry, signs/freshness/paging and substantive error/offline states.
They require real execution followed by original-pixel review; no images were
fabricated or counted as executed. CSS enlargement is not physical browser zoom.

A second independent qualification-source review reproduced six evidence/safety
issues and drove finite corrections. PostgreSQL case collection now emits only
`cases_complete`; the runner alone promotes `complete` after successful pytest
exit (including teardown) and fresh source/plan checks. Failed verification becomes
`failed`. Caddy invalidates prior success before source hashing or Docker preflight.
The disposable database guard rejects all connection query parameters, unapproved
drivers and ambient libpq destination settings. Every reset/migration/seed entry
point validates before connecting; Alembic pins and restores the validated URL.
Direct inventory PostgreSQL pytest fixtures reuse the same guard. No unsafe target
was contacted: observed negative tests inspect rejection before connection.

The review also reproduced bearer leakage in nested Playwright HTML steps despite
catching the top-level API error. Inventory fixture controls/passthrough now use a
small native HTTP boundary with exact loopback origin/path/method restrictions,
no redirects, header allowlists, 10-second/1MiB bounds and generic errors. An actual
report-only Playwright regression (no browser/account/app server) inspects stdout,
JSON and every HTML ZIP member for an environment-only noncredential canary.
The original failure was reproduced independently; the corrected report passes.
The 503 screenshot requires its exact settled alert, enabled refresh and retained
history. The preservation journey starts with a real pending local-only operation
before navigation; only that synthetic account lacks `sync.push`, so exact journal,
delivery and event comparisons do not race legitimate delivery. This is not a
lost-acknowledgement delivery-race claim. Exact product/section focus and keyboard
activation assertions replace broad descendant-focus checks.

Local correction checks: 47 Python fixture/evidence/report checks, 14 direct-PG
fixture guard checks (19 other cases deselected), and 3 native HTTP helper checks
pass without skips. Strict E2E typing/lint/format and 17-case collection pass.
These counts do not qualify actual PostgreSQL, Caddy, native browser or pixels.

The inherited main40 tree has 27 aggregate controls but retains one direct clock
retry; its 63 aggregate browser passes are not a clean-direct claim. See the dated
manual checklist for exact hosted references. Actual main41 merge
`88ee267f2d9fa1e63836ca5c9a47e49f21882fd6` is now reconciled; its exact-tree
premerge CI38681739711 passed 63 direct and 63 aggregate browser cases with zero
flaky cases, 27 controls and retry-free 20+9+5 repetitions. Its cache rollback,
offline coalescer and both admission-completion paths/tests remain intact.
Main41 postmerge gates are pending at this checkpoint. No inherited result qualifies this new source.
Exact final head/tree, full integrated results and remaining hosted gates belong in
the coordinator handoff manifest after source reconciliation and freeze.

The final runner entry-point follow-up also reproduced a hosted invocation issue:
`python scripts/ci/inventory_read_proof.py` lacked the repository root on sys.path
when no developer PYTHONPATH was present. A narrow direct-entry bootstrap and
isolated subprocess regression now reach the safe invalid-target guard. Three
runner tests and seven independent orchestration probes pass; no database or
browser is launched by this check.

The first reconciled local aggregate at `8f8aab3` retained one failed logging
assertion (2,405 Python passes, 262 explicit skips; all other 20 controls passed).
A three-test causal sequence reproduced it: an identity error creates the logger,
an Alembic migration disables existing loggers, and the inventory capture sees no
records. The focused inventory test alone passed. Its capture now explicitly
enables and restores only that logger through pytest monkeypatch, matching the
existing identity-test convention; every privacy/context assertion and production
logging byte remains unchanged. The original failure and causal RED/GREEN logs
are retained. Corrected-source integrated qualification is required.

## First hosted PR42 result and bounded diagnostic follow-up · 2026-10-15

[PR42](https://github.com/IzignaMx/open-cycling-workshop/pull/42) first source head
`ced9a493c729d242ed86c3ec0731cc358504cf95` and GitHub test merge
`dc524f22c087fadbd2989aa057d1a0102e7227b9` share exact tree
`b08a8c5b8267c0b906841d6c93635236eadeebe5`; the synthetic merge retains actual
main41 plus the published source head. [CI38686652539](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38686652539)
passed 2,654 Python tests with 14 explicit skips and three warnings. Its dedicated
PostgreSQL18 run passed all 43 cases without skips; source hashes and the measured
plan digest were verified from artifact 11950563024.

The actual lock budgets returned safe 503 at 2.016767/2.017138 seconds, the statement
budget at 5.009781 seconds and total transaction budget at 8.008180 seconds after
two individually completed three-second waits. Cleanup took 17.9–19.6ms, retained
unchanged inventory and permitted a subsequent writer and committed revocation.
On 20,001 products/100,000 movements, catalog/stock/newest/middle plans measured
57.159/27.993/52.811/36.404ms. Catalog used an external disk sort and histories used
top-N sorts after existing index scans: this proves the bounded synthetic fixture,
not general production scalability, browser latency or physical-device performance.

The Caddy runner then failed its original 30-second readiness assertion for the
first configuration. Its artifact is `incomplete`, with zero completed cases;
terminal output contains no startup cause. Preserve that failure as **cause
unproven**. Subsequent direct browser preparation/install was skipped. The separate
always-run aggregate retained **25 passed controls, one failed browser control and
one blocked benchmark**: 80 browser journeys were unexecuted, with 159 BeforeHooks
launch failures due to absent Chromium. These are setup failures, not evidence of
80 product defects or executed journeys. No original pixels were qualified.

The narrow diagnostic follow-up changes only the runner/tests/documentation. It
caps combined subprocess output during reading at 64 KiB, reaps subprocesses on
failure, and records fixed phase/health categories plus allowlisted container
status, exit code and OOM flag. Before any private synthetic query, bounded startup
logs may produce fixed error hints only. Raw logs, URI/query/header/body values,
environment and arbitrary exception text are never written to the artifact.
Original failures remain distinct from upstream/container/temporary-directory
cleanup failures; cleanup failure still prevents success. Independent review
reproduced a temporary-directory masking defect in the initial patch, corrected
with observed RED/GREEN and separate resource-release checks.

The actual production configs, 30-second readiness budget, forwarding checks,
verified TLS and private-query assertions remain unchanged. Local diagnostic
checks are not actual Caddy proof; exact changed-head hosted qualification and
remaining native browser/pixel/physical/operator gates remain open.

Final local diagnostic checks passed 29 focused cases without skips and the full
operations suite with 474 passes, three explicit PostgreSQL recovery skips and
one warning. Full Ruff check/format (250 files), repository contract and touched
document formatting passed. Independent review re-ran the 29 cases plus 14
configuration/phase probes, six failure-order combinations and real subprocess
boundary/reaping checks. A real BaseServer thread-start failure was observed RED
(deadlock), then GREEN after guarding shutdown/join until the server thread starts.
No actual local Docker/Caddy execution or changed-head hosted success is claimed.

## Production-image launch correction candidate · 2026-10-15

The second [CI38689123352](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38689123352)
tested source `74efdb7154a774a4f288c56d3429a0a444da6bfa` through merge
`743d5d345d2b5f4b55a48b6e6cf9bab11a149bf5`, exact tree
`9d9fbd83b9f6a81ae79ba80b7a3c3e1706da3188`. Artifact 11951727637 (ZIP
SHA256 `8fc64516e4f688c41e0b6df30cc0e36c2d98ed6438e400f7eaca881a27e79220`)
accompanied 2,673 Python passes (14 skips, three warnings), a separate 43-case
PostgreSQL pass and 871 aggregate core passes. The browser cascade remained 80
unexecuted journeys/159 missing-Chromium setup attempts; direct/kernel/repeat
journeys were skipped. Edge evidence retains zero completed configurations: first-config readiness exhausted with
connection refused, container exit 255, no OOM, no matched startup hint, and
successful upstream/container/temporary-directory cleanup. No raw log survived.
The original startup cause remains unproven; neither failed run is replaced by a
unit-test success or by the separate passing production-runtime job.

Static comparison found the probe used the unmodified upstream image, whereas
`infra/docker/web.Dockerfile` already removes the binary's inherited file
capability for nonroot/cap-drop/no-new-privileges operation on high ports. The
[official Caddy 2.11 image recipe](https://github.com/caddyserver/caddy-docker/blob/master/2.11/alpine/Dockerfile)
sets that capability. This is a concrete launch-mismatch hypothesis, not yet an
observed causal result. No production image recipe, config or security restriction
changes in this correction candidate.

The runner builds the existing production Dockerfile with its existing
allowlisted build context, a unique disposable tag, quiet output and a 600-second
build budget. It resolves both images to validated immutable IDs and launches the
same explicit binary-metadata/version shell command under identical flags, host
UID/GID, mounts and environment. The host UID override solely owns disposable
bind-directory/isolated-CA files; a root host UID is rejected. Both launch controls
retain read-only root, dropped capabilities and no-new-privileges. The raw image
must show the expected file capability, nonzero exit and an operation-not-permitted
hint with no version; production must show no file capability, zero exit and
v2.11.7 with no denial. Binary SHA256 values must match. Unexpected or contradictory
metadata fails closed, retaining only safe stage and validated observations.

Only then do both unchanged actual-config forwarding, upstream-down error-log,
no-store and verified-isolated-TLS probes run on the production image ID. Their
original 30-second readiness budgets start per probe, after build/controls.
Subprocess output remains capped at 64 KiB; control start/wait/log commands are
bounded to 30/10/5 seconds. All containers and the unique image tag are removed
with finite budgets, with original failures and each cleanup failure kept separate.
No raw query, headers, bodies, credentials, arbitrary errors or startup text are
published; no host capability/trust-store changes or shared cache pruning occur.

Observed local RED was 12 missing-behavior failures; the safe-observation test
added one RED. Independent review reproduced two contradictory version/EPERM
acceptances, both observed RED and corrected. An additional review diagnostic correction rejects unknown capabilities before
reporting their absence, with an observed failing-first regression. Final focused
checks passed 46
without skips; full operations passed 493 with three explicit PostgreSQL recovery
skips and one warning. These are harness/control-flow results. Docker is absent
locally: the paired causal result, two actual Caddy configurations and exact-head
native browser/pixel gates remain pending. Physical/operator gates remain open.

Independent exact-source review re-ran all 46 focused cases plus 34 adversarial
control permutations and eight original/directory/image failure combinations,
with no remaining source blocker. Full local Ruff check/format (355 files),
repository contract, touched Prettier and diff checks passed. These agent-authored
changes and independent agent reviews are not human GitHub approval.

## Actual paired edge proof and kernel-fixture correction · 2026-10-15

[CI38691900346](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38691900346)
source `b3f5ac5ddbabe4fd361d1e743a3da4de749611d8`, test merge
`0d576c50f5073bdd93346598455f756a8ab057f3`, exact tree
`5ac86e7543f5a724358cffaf51b12c79ae52afcb`, completed both actual Caddy
configurations and the 43-case PostgreSQL proof. Independently reviewed artifact
11952507761 has ZIP SHA256
`595588c13333098706bd904c7539b4734e280e8393fbdf0d6eb28e3c2adc9f36`;
all eleven edge/database source hashes were bound to the tested merge.

Both launch controls used binary SHA256
`678ade3bfc088749c81a681adc603333ee0bb023b6a6cfe3c0f58bef8ff854e9`.
Under identical nonroot restrictions, raw upstream retained
`cap_net_bind_service=ep` and failed with exit 126/operation-not-permitted;
the production image had no file capability and returned v2.11.7/exit zero.
Both actual configs preserved forwarding and unrelated queries, excluded all
private query canaries and retained six required runtime errors. LAN used a
verified isolated CA. Container, image and temporary-directory cleanup completed.
This proves the tested launch incompatibility and correction; it does not
reconstruct the exact historical exit-255 cause from the discarded original logs.

The PostgreSQL artifact contains all 43 expected cases. Observed actor/org lock,
statement and total budgets were 2.018450/2.016191/5.010165/8.008108 seconds, with
17.907–19.613ms cleanup, unchanged inventory and successful successor writes and
revocation. Catalog/stock/newest/middle plans were 57.453/28.085/53.031/35.512ms on
20,001 products and 100,000 movements. The prior sort/scan, synthetic-load and
non-production-performance limitations still apply.

After successful Chromium installation, the isolated kernel browser step failed
before the direct 80-journey run. Local execution reproduced immediate baseline
server failure: it creates an owned temporary SQLite database but called the
shared URL-taking seed helper, whose new PostgreSQL-only guard correctly rejects
SQLite. The local CLI RED is retained. Hosted terminal traceback binding remains
pending at this source checkpoint; the aggregate is not claimed successful.

The correction leaves every shared PostgreSQL guard and browser assertion intact.
The kernel server seeds its two fixed identities directly through a Session bound
to its internally created temporary engine, with no external URL parameter or
SQLite exception to the shared guard. IDs, names, wildcard capabilities, session
version and protocol floors remain equivalent. An engine finally clause covers
schema/seed/app-construction/serve failures. Tests prove both logins, untouched
ambient existing SQLite files and rejection of direct shared-helper SQLite misuse.
Observed regression RED was four failures/one pass; focused GREEN is 35 passes.
The isolated kernel bundle builds and all 14 browser cases collect; neither result
claims native browser execution.

A real CLI process reached HTTP readiness and exited zero on graceful SIGINT,
removing its owned temporary directory. A separate first smoke incorrectly expected
exit zero on SIGTERM; that failed assertion is retained, with missing original
numeric status explicitly recorded rather than reconstructed. A new bounded
non-qualifying diagnostic observed SIGTERM exit -15 and a directory remaining
until the outer smoke owner removed it. Uvicorn restores/re-raises that signal;
this inherited SIGTERM/SIGKILL limitation is not changed by the fixture fix.
Exception cleanup and graceful SIGINT cleanup are distinct, bounded claims.

Corrected-head hosted kernel/direct/repetition/aggregate browser and pixel proof
remain required. No real installation, account, persistent database or operator/
physical-device gate is claimed by this temporary-fixture correction.

Final affected fixture/operations checks passed 538 with three explicit PostgreSQL
recovery skips and one warning. Full Ruff check/format (356 files), repository
contract, touched Prettier and diff checks passed. Independent source review found
no blocker and inspected the recorded RED/GREEN and signal evidence; it did not
rerun those tests. This is agent-authored code and agent review, not human approval.

## Terminal browser evidence and main43 reconciliation · 2026-10-15

The terminal [CI38691900346](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38691900346)
log confirms the kernel fixture traceback at 06:31:33: baseline-server calls
seed_browser_identity, then validate_e2e_database_url rejects its SQLite URL.
Its direct Python run passed 2,692 with 14 skips. The separate kernel startup
failure skipped the direct 80-journey phase, but the always-run aggregate really
executed all 80 journeys: **77 passed, three failed, zero flaky/skipped cases**.
Each of the three failed twice. This does not inherit the earlier two runs'
missing-Chromium setup diagnosis. The dedicated PostgreSQL/Caddy success above
remains valid for its exact preceding tree, not automatically for the new merge.

Aggregate artifact 11953836445 is 242,029,278 bytes, SHA256
`bdce82c6daef00b08237fb50658a7cccef96fab8fc9db68c789461c0abad36e6`.
Its CRC, 691 safe unique paths and embedded Playwright report were checked. The
retained failures are:

1. Administration narrow-reflow expected eleven labels but correctly rendered
   twelve after adding Inventario. Both captured Banco320 geometry records show
   complete visible identity, no longest-word overflow and all six navigation
   labels on one line. The obsolete count stopped the remainder of that journey.
2. Inventory preservation expected at least one event before any delivery attempt.
   Customer creation supplies localEvents: []; this account lacks sync.push and
   its durable operation is pending. The failure occurred before draft/navigation/
   offline/reload assertions, so those behaviors were not proved by either attempt.
3. Banco timed out opening the next appearance scene. Playwright check() returns
   immediately for an already checked radio ([official locator contract](https://playwright.dev/docs/api/class-locator#locator-check));
   Banco is the default, so focus stayed on the disclosure trigger. Escape is
   handled inside the panel, as exercised by the existing structural-theme tests.
   The next toggle closed the still-open panel and hid its surface selector.

The two-file correction replaces assumptions, not product behavior. Administration
now compares exact ordered identity/settings/four-metric labels and all six link
labels/hrefs. Inventory positively checks the exact created journal row, one
pending delivery with unresolved=1, attempts=0, null attempt/result, the correct
empty history, and no observed non-read API request from before creation through
navigation, disconnection and reload. Full journal/delivery/history equality is
retained at every boundary. The unsent name remains checked while mounted,
including disconnection; this does not promise unsubmitted form persistence after
page reload. Reload still must retain durable pending work and hide volatile
inventory. Connected local-only and offline status messages are checked separately.

Each theme now selects a focused radio using Space, asserts checked/focused,
presses Escape, then requires hidden panel, collapsed trigger and returned focus.
This preserves the established keyboard-in-panel contract, including default
Banco. It does not remove Escape or change product focus handling, test timeouts,
retry policy, complete-word/target-size/reflow/axe checks or screenshot privacy.
Original failed attempts remain retained; the failed inventory cases captured no
pixels because they stopped before their assertion-backed captures. Selected
retained administration pixels were inspected; that is not full visual acceptance.

Local focused verification passed 871 frontend core tests, web and explicit
strict two-file E2E TypeScript checks, ESLint, Prettier and diff checks. Playwright
collected 33 affected cases; none ran locally. Hosted RED is observed; corrected
native GREEN remains required. Independent agent review inspects the exact
source, recorded results and actual failures; it is not human GitHub approval.

Actual main43 `d9381808c61b4682844666eb62967ccbf9afc5b9`, tree
`ac1e5985e7bb89a274755e9ab0bcb2d1ec35778a`, is reconciled by local merge
`bcde3c9eb7478a25d1aed7c86e1e5d1f2ce04079` with that real second parent.
Both additive documentation histories are retained; every incoming quote source,
test, plan, ADR and evidence blob exactly matches main43. No new quote work is
part of this correction. Exact combined hosted kernel/direct/repetitions/aggregate,
PostgreSQL/Caddy, runtime/security/native/build and pixel proof remain required.
Physical-device/operator gates and the inherited signal-cleanup limits remain open.
