# Connected inventory read

This feature owns no authentication, baseline, IndexedDB store or write queue.
The runtime's connected-read facade supplies a fresh account/workshop capture.
An explicit entry verifies context and fetches one 50-row catalog page; selecting a
product independently fetches its derived available quantity and one 50-row movement
page. Older replaces history; Newest resets it. Refreshing stock leaves history's
receipt time unchanged. There are no automatic retries or cross-module enrichments.

The runtime checks actual operational kernel ownership before each dispatch and
before publishing success/error/refusal. Synchronous account/scope/mount/request
fences additionally reject stale success and errors, including A→B→A. Account-only
users use `/auth/context` metadata without `sync.pull`, offline admission or baseline.
Expiry, rollback, offline, logout and invalidation clear volatile data. Explicit
reverification can recover a permitted metadata-only directory after 403.

Transport bounds body bytes and time, verifies no-store/JSON/closed scope-specific
shapes, and inspects raw number lexemes before JSON parsing. Fractions/exponents,
unsafe integer quantities and noncanonical cursors cannot become rounded values.
New history order uses exact microsecond strings and Unicode code-point ID order.
Current 401/403 precede untrusted headers/body; obsolete refusals have no effect.

The panel uses existing theme tokens/density, plain text, separate status/error
announcements and paging focus. In-page navigation keeps unsent operational forms
mounted. The November 25 audit records 17 locally executed native inventory
cases with zero retries, including four-theme scenes, for its dated source.
See the [source-bound receipt](../../../../../docs/10-spec-development/2026-11-25-project-inventory-audit.md).
Later source changes require their own proof; these browser results do not replace
physical-device or assistive-technology acceptance.

Tests: `tests/inventory`, `tests/runtime/connected-read.test.mjs`, and
`e2e/inventory.spec.ts`. The repository ADR freezes the interface; native browser,
PostgreSQL, Caddy and actual pixel qualification remain separate gates. Full offline
inventory, mutation/reconciliation and quotes are not implemented here.

Browser evidence keeps credentialed fixture traffic out of Playwright APIRequestContext
and route.fetch error steps. A bounded native test-only helper is checked against an
actual HTML report ZIP, without launching a browser. The preservation fixture uses
an explicitly local-only operational writer so pending work exists before inventory
entry and stays unchanged through disconnect/reload. These are authored journey
assertions; report privacy execution alone does not qualify the browser journey.

The catalog has a transient, page-local name/SKU substring filter. It never queries
other pages or stock; original page size still controls pagination. New page,
refresh or access loss resets the query, while stock/history updates retain it.
No matching rows is distinct from an empty server page. See the
[bounded evidence](../../../../../docs/10-spec-development/2026-11-11-inventory-page-filter.md)
for browser and physical acceptance limits.

Catalog action names include the visible **Consultar producto** caption followed
by the product name and **SKU** value. Same-name products with different SKUs
therefore have distinct accessible action names; selection still uses each row's
product ID. Existing displayed/authorized text is reused with normal escaping,
without extra requests or local persistence. The [November 26 source-bound
qualification](../../../../../docs/10-spec-development/2026-11-26-inventory-accessible-actions.md)
records component/native RED then seven component and 17 native passes with zero
retries, including exact product-ID keyboard selection in all four themes.
This is synthetic browser evidence; manual voice-control/screen-reader and
physical-device qualification remain separate.

A failed catalog or history page exposes an explicit **Volver a consultar esta
página** or **Volver a consultar estos movimientos** action. It retries the
current failed offset/boundary through the same guarded read method; it does not
reverify the account, retry automatically or preserve stale data. Ready/loading/
cleared states and authority refusals do not dispatch retry work. Current access,
capability, scope, request and product fences still apply, including invalidation
while a retry is pending. History retry keeps the independent stock receipt.

**Actualizar catálogo** and **Movimientos más recientes** still reset their
traversal. Retry retains query position, not a snapshot or guaranteed identical
rows. The [November 26 retry evidence](../../../../../docs/10-spec-development/2026-11-26-inventory-page-retry.md)
records native baseline failure and 17 candidate passes with zero retries,
including Enter/Space recovery, exact request positions, heading focus and narrow
error-state controls. Exact successor hosted and physical acceptance remain
separate; the connected-only inventory contract is unchanged.

The [workshop-scope correction](../../../../../docs/10-spec-development/2026-11-26-inventory-workshop-scope.md)
keeps directory controls specific to eligible account-only reading. An operational
reader continues to use the selected operational workshop. Directory navigation
or replacement must invalidate a previous inventory selection and its volatile
readings before another current-directory choice is admitted; the visible choice
must not become empty while an earlier location's reading remains displayed.
An inventory-owned directory read also blocks selection, verification and duplicate
directory actions until it settles. The final local evidence includes 137 focused
cases and 17 native inventory journeys, all passing. Hosted qualification remains
separate. No inventory authority, operational selection, API, local persistence or
offline contract changes are implied.

The later [PR126 scoped merge receipt](../../../../../docs/10-spec-development/2026-11-26-inventory-page-retry.md#pr126-scoped-acceptance-and-merge--2026-11-26)
records 17 inventory cases passing once in each hosted browser phase. The
[PR127 stacked receipt and retarget](../../../../../docs/10-spec-development/2026-11-26-inventory-workshop-scope.md#pr127-stacked-evidence-and-retarget-to-main--2026-11-26)
independently records another 17 single-attempt inventory passes in each phase
for its own exact source. Full-suite login-body failures remain preserved;
neither scoped result implies global retry-free acceptance. The retargeted
documentation successor still needs its own exact hosted qualification.

The [PR127 retargeted acceptance and merge](../../../../../docs/10-spec-development/2026-11-26-inventory-workshop-scope.md#pr127-retargeted-acceptance-and-merge--2026-11-27)
subsequently qualifies that former documentation successor and records main
`971bdd2`. Both reviewed browser reports contain 17 first-attempt inventory
passes within 146 total passes. This supersedes the earlier PR127 retargeted
pending statement only; fresh-main and later-source evidence remain separate.
