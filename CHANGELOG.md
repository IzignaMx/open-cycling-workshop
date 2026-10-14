# Changelog

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
- Browser acceptance and screenshots are added; hosted/physical verification
  remains pending until recorded for the exact implementation.

Relevant changes for operators, developers and integrations. Development work
below is unreleased; it does not declare V0.1 physically qualified or V1.0 ready.
Core/API version identifiers retain the current development baseline until an
explicitly qualified release. Changes follow Conventional Commits and DCO;
release versions follow the Engineering specification's SemVer policy.

## Unreleased

### Added

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

- Migration test setup excludes ambient application URLs and secret-file
  fallbacks. PostgreSQL infrastructure tests validate dedicated loopback targets
  and pin the raw test URL during Alembic execution; no runtime resolver behavior
  changed. No-network regressions cover target isolation and redacted rejection.

- Sync pulls enforce the authenticated location when no location is requested
  and filter each known entity by its read capability before pagination. Unknown
  feed types are denied by default; see the
  [scope and cursor decision](docs/02-technical-architecture/2026-10-14-sync-read-authorization.md).

- Inventory commands derive actor/organization/location server-side and reject
  client overrides. Canonical Unicode SKU lengths, bounded pagination and NUL
  text validation prevent malformed requests from becoming storage errors.

### Compatibility and operations

- Inventory mutations are online commands; no offline stock promise, quote UI,
  public deployment or new release is included.
- Whole-reservation finalization only; partial finalization is explicitly
  rejected. CONSUME responses represent the hold entry; read the stock endpoint
  for the net available balance.
- No historical ledger rows are rewritten or inferred. Quote-table migration
  remains future work and now uses the next revision, 0008.
- Task 3 verification evidence is tracked in PR #22 and
  [execution status](docs/10-spec-development/execution-state.yaml).
  Physical Windows/Android and other manual V0.1 gates remain open.

### Integration

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
