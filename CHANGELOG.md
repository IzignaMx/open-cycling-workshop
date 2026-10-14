# Changelog

## Unreleased · Ordered supported change-feed writers

- Customer/bicycle/order REST creates and order transitions now publish the same
  complete projection and outbox event as sync, atomically with domain changes.
- Supported writers serialize per organization before domain reads and cursor
  allocation, sharing administration's lock; HTTP writes refresh actor/session
  authority after waiting and enforce contracted grants/scope, preserving the
  existing literal wildcard-intersection policy.
- Existing numeric feed and REST contracts stay compatible. Historical REST-only
  records still need a baseline. This does not activate a multi-user offline
  cache, backfill inventory/quotes, or fence old server/browser writers.
- First-head hosted PostgreSQL ordering coverage passed; final main30
  reconciliation awaits exact combined-tree hosted qualification.

## Unreleased · Isolated offline identity kernel

- Additive isolated Dexie v5 factory and identity-bound local repository kernel,
  with immutable authored-operation journals, separate delivery history and
  transactionally fenced command/acknowledgement boundaries. Independent review,
  first-head hosted/native-browser proof and the pending main-29 reconciliation
  gate are recorded in the [increment record](docs/10-spec-development/2026-10-14-isolated-offline-identity-kernel.md).
- New isolated contexts remain `BASELINE_REQUIRED`. The production App/default
  singleton and Golden Slice remain v4; authentication-context, complete baseline
  and ordered-feed integration are not implemented. Live shared-browser
  isolation and offline-permission risks remain open; there is no rollout claim.
- Preserve all eight existing stores, personal preferences/logos and unattributed
  legacy queued work. The kernel does not claim, replay or delete legacy rows;
  its [ADR](docs/02-technical-architecture/2026-10-14-isolated-offline-identity-kernel.md)
  records the future activation and operator recovery gates.
- Document the native-Chromium-confirmed Dexie v4-to-v5 old-bundle reopen/write blocker; no
  production activation or schema-version-only fencing claim.
- Move the unimplemented offline quote schema reservation from v5 to v6.
  Administration Alembic 0008 and future quote PostgreSQL 0009 remain unchanged.
  No new credentials, server/wire contract or actual installation upgrade.

## Unreleased · Structural personal themes

- Four structural workshop layouts in Personalización: Banco de trabajo (default),
  Plano técnico, Ritmo modular and Turno nocturno, with twelve curated palettes,
  independent surface schemes and larger Workshop Mode controls.
- Versioned personal preferences in an additive Dexie v4 store; appearance is
  user/organization-local, and a safe offline raster logo also belongs to the
  current location. Shared organization branding and sync are not implemented.
- Shared forms/operations remain mounted during theme changes; order transition
  controls consistently honor the existing orders.write capability.
- Session-generation guards reject late view updates from a previous login or
  scope, preserving current-user conflict/customer context.
- Cached customer/order summaries and per-entity conflict contents require explicit
  read permissions in every theme. Restricted users retain durable records/queues;
  offline permission freshness and safe cache revocation/resnapshot remain pending.
- Conflict types now come from the matching durable queued mutation rather than a
  hardcoded customer label. Legacy ambiguous records stay stored but their details
  are hidden; mismatched/unknown responses cannot acknowledge pending mutations.
- Browser acceptance and screenshots are added; hosted/physical verification
  remains pending until recorded for the exact implementation.

Relevant changes for operators, developers and integrations. Development work
below is unreleased; it does not declare V0.1 physically qualified or V1.0 ready.
Core/API version identifiers retain the current development baseline until an
explicitly qualified release. Changes follow Conventional Commits and DCO;
release versions follow the Engineering specification's SemVer policy.

## Unreleased

### Added

- Bounded server-side local user, starter-role and workshop-location
  administration, with optimistic account versions, session revocation and
  credential-change endpoints. See the
  [scope and acceptance record](docs/10-spec-development/2026-10-14-access-administration.md)
  for evidence and remaining gates; no administration UI or release is claimed.
- Explicit `ocwpctl access create-first-owner` setup creates a separate
  organization-wide owner from a password file. It refuses any existing owner
  record, including inactive owners; existing bootstrap behavior is unchanged.
- Pure quote domain with immutable labor/part/tax/discount lines, integer-minor-unit
  totals, explicit currency, deterministic rounding and scoped discount allocation.
- Quote revisions preserve historical prices, totals and line data. Persistence,
  authorization, API and offline quote editing remain future increments.

- V0.2 Increment 2 Task 3: capability- and location-scoped inventory product
  creation/listing, derived stock reads, and server-authoritative movement API.
- Required UUIDv7 movement IDs provide idempotent command replay. PostgreSQL
  product locks serialize stock reservations and terminal finalization.
- Migration 0007 adds a unique reservation-finalization guard. Existing duplicate
  terminal references block the upgrade without altering history; see the
  [migration and recovery ADR](docs/02-technical-architecture/2026-10-13-inventory-command-atomicity.md).

### Fixed

- Sync chaos setup now waits for durable baseline acknowledgement and proves the
  server baseline/version before constructing the three-operation conflict batch.
  A deterministic delayed-completion/ACK regression and retry-free CI repetitions
  guard the setup race. Hosted red-to-green evidence and ten retry-free
  repetitions are recorded in draft PR #24.

- Consumption now commits its hold finalization and physical stock deduction
  atomically through the API; consuming a reserved item cannot replenish stock.
- Reservation-finalization lookup uses reservation reference IDs and recognizes
  both RELEASE and CONSUME, including distinct command IDs.
- [PR #21](https://github.com/IzignaMx/open-cycling-workshop/pull/21), merged
  2026-10-13: scoped sync payload validation preserves whole-page rollback and
  durable cursors across rejected changes, reload and recovery.

### Security

- `/auth/me` reports revalidated effective session grants and location without
  widening token authority; it serializes its account read with administration.
- Sync service-order transitions attribute new events to the authenticated
  submitter, ignoring legacy payload actor claims. Existing receipt replays must
  match the stored organization/location/entity/operation tuple; mismatches
  become isolated conflicts. Blank or whitespace-containing envelope IDs are
  rejected before effects so domain normalization cannot break identical retry;
  malformed historical receipts remain preserved for explicit reconciliation.
  No receipt actor/digest or client-cache isolation is
  claimed. See the [scope and evidence](docs/10-spec-development/2026-10-14-effective-identity-sync-authority.md).

- Migration test setup excludes ambient application URLs and secret-file
  fallbacks. PostgreSQL infrastructure tests validate dedicated loopback targets
  and pin the raw test URL during Alembic execution; no runtime resolver behavior
  changed. No-network regressions cover target isolation and redacted rejection.

- Administration checks persisted actor/session and old/new target scope/grants
  after acquiring an organization lock. Protected owner designation is separate
  from the `Owner` role bundle; the last active recovery-capable owner cannot be
  removed. New grant snapshots accept only implemented concrete capabilities.
- Sensitive account/session/location changes commit with a secret-free
  append-only audit event. Security changes revoke sessions; name-only changes
  increase account version without revocation. Credential validation errors are
  redacted and sensitive identity/administration request correlation is
  server-generated. Ordinary health request-ID behavior is unchanged.
- Sync pulls enforce the authenticated location when no location is requested
  and filter each known entity by its read capability before pagination. Unknown
  feed types are denied by default; see the
  [scope and cursor decision](docs/02-technical-architecture/2026-10-14-sync-read-authorization.md).

- Inventory commands derive actor/organization/location server-side and reject
  client overrides. Canonical Unicode SKU lengths, bounded pagination and NUL
  text validation prevent malformed requests from becoming storage errors.

### Compatibility and operations

- Identity migration 0008 follows 0007 and adds owner/version metadata and audit
  guards without promoting users or widening existing grants/location scope.
  Invalid legacy session versions block for reviewed remediation. Follow the
  [upgrade and recovery boundary](docs/02-technical-architecture/2026-10-14-access-administration.md).
- Before end-user permission-management rollout, browser state must be isolated
  by user/capability/scope and cursors safely resnapshotted/backfilled while
  preserving pending mutations. Server revocation alone does not satisfy that
  gate. Organization-wide owners remain API-only pending workshop-selector UI.
- Inventory mutations are online commands; no offline stock promise, quote UI,
  public deployment or new release is included.
- Whole-reservation finalization only; partial finalization is explicitly
  rejected. CONSUME responses represent the hold entry; read the stock endpoint
  for the net available balance.
- No historical ledger rows are rewritten or inferred. Quote-table migration
  remains future work and now uses revision 0009 after identity 0008; the earlier
  quote reservation of 0008 is superseded without an empty migration or branch.
- Task 3 verification evidence is tracked in PR #22 and
  [execution status](docs/10-spec-development/execution-state.yaml).
  Physical Windows/Android and other manual V0.1 gates remain open.

### Integration

- Access administration includes merged PR #26 main `c1e2230`, runtime PR #25
  (`0342799`) and migration target-isolation fixes. Its initial PR #27 checkpoint
  `0c37d46` passed PostgreSQL 18.4 CI: 812 Python tests (three explained skips),
  74 frontend core tests, 30 browser executions (10 direct, 10 repeated sync,
  10 qualification) and 27 aggregate checks. All four Local runtime jobs passed, including actual
  backup/restore and three ARM64 image builds. Final integration-head CI and
  browser account/grant/scope cache reconciliation remain separate gates; no
  physical hardware, complete permission UI or production rollout is claimed.
- PR #22 inventory API integrated on 2026-10-14 after fresh independent code review
  and exact-head CI/Security/DCO. Quote Task 4 passed combined-tree CI
  and independent review and was integrated through PR #23; no complete quote workflow or stable release is claimed.

### Local workshop MVP foundation (pending hosted qualification)

- Define the laptop-to-ARM64 workshop MVP sequence, preserving existing tenant/capability and offline-first architecture.
- Add file-based database URL configuration and prevent service-worker navigation fallback from converting API/health routes into application HTML.
- Add isolated local Caddy/PWA/API/PostgreSQL/worker Compose, separate LAN TLS,
  non-superuser application database role and locked amd64/arm64 build paths.
- Add snapshot-consistent PostgreSQL bundles, integrity manifests and guarded
  fresh-target restore; database-only evidence excludes browser queues and assets.
- Local runtime and recovery qualification are tracked in the execution state; this is not a stable release or physical Raspberry qualification.
- Inventory API PR #22 and quote-domain PR #23 are merged; full quote workflow remains future work.

### Qualification reliability

- Inventory PostgreSQL test setup now passes raw percent-encoded URLs to the
  shared migration configuration, avoiding double escaping. A no-network
  regression checks the exact URL and decoded synthetic password before any
  engine can connect; production secret-file handling is unchanged.
