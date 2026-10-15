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
mounted. Four-theme browser scenes are authored, not yet locally executed.

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
