# Scoped pull integrity hardening

## Specification and acceptance criteria

This corrective increment implements the existing R01-T020 durable client merge
contract and the Workshop Core implementation plan's Task 6 scope-isolation
acceptance criterion (`docs/superpowers/plans/2026-08-31-v0.2-workshop-core.md`).
It does not open a new release scope.
Normative sources: Master Agent Loop v0.2 §11; Technical Architecture v0.2 sync
protocol; Security/Privacy §§9–10; QA TC-SYNC-008 (incompatible payload without
local loss) and OFF-007 (local persistence). TC-SYNC-003 requires a **server**
restart between batches and is not proven by these client-reload journeys.
The normative R02-T006 concerns offline intake photographs; the historical
execution-state mapping uses that ID differently and is not a normative source
for this increment.

1. Every change envelope must match the active organization and location,
   including entity types the client does not yet recognize.
2. Every recognized customer, bicycle and service-order change must have a
   payload whose organization and location independently match the active scope.
   Missing payload/scope is rejected; foreign data is never relabeled as local.
3. Rejection leaves the entire page's entity writes and durable cursor unchanged.
   The existing Dexie transaction supplies this atomicity, including rollback of
   valid writes earlier in the same page.
4. Reload retains the last valid page/cursor. A corrected page can subsequently
   merge and advance, and survives another reload.
5. Same-scope unknown entities retain the existing forward-compatible skip
   behavior. Server serializers already supply the required scope fields.

No schema migration, protocol change, dependency or new ADR is needed. This is
an enforcement fix for the accepted Dexie/scoped-sync architecture.

## Regression and evidence

- Core regression: `apps/web/tests/sync/merge-workshop-core.test.mjs` covers
  missing/foreign organization/location in both envelope and payload for each
  recognized entity, missing payloads, and foreign unknown-entity envelopes.
- Pre-fix core run: 72 tests, 59 passed, 13 failed. The failures include missing
  rejection and the former generic diagnostic for missing customer scope.
- Post-fix core run: 72 passed, zero failures.
- Local aggregate qualification: 21 checks passed, zero failed, five explicitly
  blocked; 176 Python tests passed and one PostgreSQL integration test skipped.
  Repository contract, runtime HTTP smoke (SQLite), Python lint/format/mypy,
  frontend lint/format/typechecks, generated contracts and production PWA build
  passed. Playwright discovery lists all nine tests, including the two new tests;
  discovery is not execution.
- Production-PWA journey: `apps/web/e2e/sync-scope-integrity.spec.ts` injects a bad
  change-feed page after a valid customer, checks rollback of an earlier customer
  update and the cursor, reloads, corrects the page, and verifies durable recovery
  separately for bicycle and service-order payloads. Authentication and IndexedDB
  remain real; only the change feed is fault-injected.
- The core tests use table fakes and **do not prove transaction rollback**. The
  Playwright tests are the required evidence for browser atomicity/reload.

Local browser execution is blocked by the managed Chromium URLBlocklist;
PostgreSQL integration is unavailable in this workspace (no server or Docker).
Do not interpret local unit/static/build checks as browser/PostgreSQL evidence.
The draft PR's hosted CI must validate the browser journey on the exact head.
Physical Windows/Android, storage pressure, and broader release qualification
remain separate gates in the manual checklist.
