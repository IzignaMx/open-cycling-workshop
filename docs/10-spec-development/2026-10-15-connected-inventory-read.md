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

The inherited main40 tree has 27 aggregate controls but retains one direct clock
retry; its 63 aggregate browser passes are not a clean-direct claim. See the dated
manual checklist for exact hosted references and the independent PR41 rollback
correction awaiting reconciliation. No inherited result qualifies this new source.
Exact final head/tree, full integrated results and remaining hosted gates belong in
the coordinator handoff manifest after source reconciliation and freeze.
