# Inventory expiry fixture observation correction

Status: bounded contract independently accepted before implementation; source
implemented, independent source review and exact-candidate hosted proof pending.
Base: merged main42 `5ab7dd7c21b9540db7cf9c4df63a3201239251fd`, tree
`fadb25559dcacbd41bbac6ec31bf71fdebb7cc7c`. Date: 2026-10-15.

## Observed failure and scope

[Postmerge CI38710698436](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38710698436)
passed the direct 80 journeys, but mandatory retry-free expiry repetition produced
nine passes and one idle-expiry failure. Chromium's CDP response-body retrieval
failed at the observer before that attempt selected a product or advanced its
clock. Its generic navigation hint does not prove navigation; no explicit navigation is observed in recorded test
steps between response arrival and failure. Immediate CDP retrieval, introduced
before PR42 merged, is demonstrably insufficient. Keep this failure and the
prior failures; premerge ten-pass evidence does not qualify postmerge repetition.

This is a test-fixture-only correction for INV-R07/R09/R10 in the
[connected-read plan](2026-10-15-connected-inventory-read.md) and its
[accepted ADR](../02-technical-architecture/2026-10-15-connected-inventory-read.md).
Production expiry, clocks, authority/admission, fetch options, grants, protocol,
storage and UI remain unchanged. The existing exact delta-read exemption is
unrelated and retained. No new API request or production test hook is introduced.

## Frozen candidate interface and lifecycle

- Add `installInventoryContextObserver(page): Promise<void>` in the existing
  E2E helper/declaration. Call it before navigation/login in exactly the two
  floor and two expiry journeys. Runtime captures `window.fetch` at bootstrap,
  so installing after login cannot observe the fetch actually used by the app.
- Retain `observeInventoryContext(page, locationId, action)` and its return shape
  `{expiresAt: number, snapshotProtocol: null | 'baseline-v1'}`. Allow exactly
  one armed observation per installed page; arm its fresh
  scope immediately before the intended action. The original full action and
  readiness assertions must finish successfully before metadata is returned.
- A fixture-owned init script wraps native fetch. Pass through the original
  arguments, receiver, signal, rejection and original Response. While armed,
  match only the same-origin exact GET `/api/v1/auth/context` with one matching
  `selected_location_id`. Require status200, exact response URL and no redirect.
  Count matching requests so ambiguity cannot silently choose one response.
- Start reading one clone at response arrival without awaiting it before
  returning the original Response. Bound accepted body bytes and the explicit
  accumulation buffer to 16 KiB, matching the
  product context limit in `apps/web/src/runtime/connected-read.ts`
  (`readBoundedJson` with limit16384). Native stream/tee chunks, decoding and
  parsed objects allocate additional memory; this is not a total-memory cap.
  Parse transiently; retain/export only finite parsed
  `offline_until` milliseconds and validated `snapshot_protocol`, after checking
  the exact selected location. Do not expose headers, token, raw body, unrelated
  fields, arbitrary error strings, URLs or storage. Instrumentation adds overhead;
  identical timing is not claimed.
- Finish after action readiness, requiring exactly one successful matching
  observation. Missing, duplicate, redirected, invalid/oversized/truncated or
  unreadable data fails closed with a fixed generic observer error. No CDP body
  calls, fallback expiry, synthetic response, retries or enlarged timeout.
- Attempt cleanup on every exit: while the page remains reachable, disarm,
  erase captured state and cancel any clone reader on success or failure. Page
  closure can prevent evaluate-based cleanup; retain the original action error
  or fail a previously successful observation with a generic cleanup error.
  Restore the original global fetch only if our wrapper still owns it, and remove
  the fixture control. The registered init script remains on this disposable
  Playwright page and runs again for a new document after navigation; no claim
  is made that every installed hook is physically removed.
  The application's already-captured wrapper reference remains inert pass-through
  until that disposable page closes; replacing it would require a product hook.
  Requests begun before arming or completing after disposal cannot satisfy a new
  observation. Reuse of a disposed observer fails rather than returning old data.

## Required RED/GREEN and qualification

Preserve the original helper bytes and actual hosted failed artifact. Reproduce
CDP-body-unavailable at response arrival while a real Fetch Response still exists
inside the page. Unit-test the in-page function under a separate VM with actual
Fetch Response/ReadableStream semantics: original response/arguments/receiver and
errors preserved; complete action readiness; scalar-only result; scope/method/
origin/status/redirect/duplicate filtering; zero/multiple response rejection;
malformed, oversized and failing stream errors; disposal on action/read failure;
late/unarmed isolation; no extra requests or CDP calls. Mocks establish fixture
ordering/privacy behavior, not a proven Chromium root cause.

Run focused tests, all affected core/type/lint/format checks and genuine Playwright
collection. Independently review frozen source/test/workflow bindings. Publication
requires a separate PR from actual main42. Hosted qualification must execute all
80 journeys, the unchanged mandatory two expiry journeys × five with retries0,
workers1 and 45-second test timeout, plus the full required matrix. Failed/skipped
repetition must still fail both its dedicated gate and final aggregate step.
Native browser/PG/Docker and physical acceptance remain unproven locally. No new
product increment begins in this correction.

## Evidence checkpoint

The independent contract review preceded source edits. The preserved original
helper and RED harness produced eight failures/one pass with CDP bodies unavailable
at response arrival while an actual Fetch Response existed in the page VM. Twelve
focused tests pass after correction. They cover real Response/ReadableStream
semantics inside the VM, including exact16 KiB acceptance, larger/invalid bytes,
missing body, synchronous/asynchronous fetch rejection, stalled-clone cancellation,
late results, ambiguity and cleanup-error handling. A cleanup failure cannot hide
an existing action error or qualify an otherwise successful observation. These
checks establish the fixture contract; they do not prove a Chromium root cause.

The exact-source frontend core suite passes883 checks; affected CI/repository
checks pass105. Strict inventory E2E typing, full frontend lint, touched formatting,
repository contract, production build and isolation checks pass. An initial Python
invocation used a nonexistent test path and ran no tests; the corrected existing
CI/repository paths produced the stated105 passes. An intermediate cleanup
implementation failed the existing unsafe-finally lint rule; it was restructured
without suppressing that rule. Both failed attempts remain retained.

Genuine ten-instance Playwright collection passes.
Collection executes no browser journey. The unchanged mandatory gate still requires
two exact titles × five, workers1/retries0/45 seconds, fresh source/report bindings
and successful dedicated plus final checks. The new observer remains outside the
production build; no production or workflow source was changed.

Postmerge evidence for the original main42 is retained separately: direct80,
aggregate80,27 verifier controls, Python2,861/14/3 with completed teardown, core877,
PG43/Caddy and inherited kernel/repetition/recovery/build checks pass. Mandatory
expiry9/1 makes the overall postmerge workflow failed. Its original artifact11961592309
has ZIP SHA-256 `a46f1d48a68758c1a573743660abc6a0bb1334ca3acde895d341362c8b27eeb3`.
The failed attempt's product-selection/clock/clearing assertions were not reached.
All earlier failures remain evidence; the new candidate has no native GREEN yet.

Local verification uses Python3.13.5, Node24.19.0 and reused dependencies with
source/import and output paths bound to the fresh worktree. It is not a fresh
pinned Node22.16/pnpm11.17 installation or hosted/native qualification. The only
production-build warning is the existing large-chunk warning. Full Python/product
and actual PostgreSQL/Docker/browser gates will run in the candidate's hosted
matrix; no repeated local aggregate is claimed for this fixture-only correction.
