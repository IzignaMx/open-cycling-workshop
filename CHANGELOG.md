# Changelog

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
  and exact-head CI/Security/DCO. Quote Task 4 remains subject to combined-tree CI
  and review in PR #23; no complete quote workflow or stable release is claimed.
