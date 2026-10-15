# Open Cycling Workshop Platform

Open source, local-first, offline-first operating platform for bicycle workshops, stores, cooperatives, fleets, and cycling-related service organizations.

> Status: **V0.1 automated foundations have hosted evidence; physical Tier 1 qualification and manual reviews remain open. V0.2 Workshop Core increment 1 is complete; increment 2 adds inventory products/ledger and the scoped inventory API.** This repository is not a production release. See [changelog](CHANGELOG.md) and [execution status](docs/10-spec-development/execution-state.yaml) for implemented scope and verification limits.

## Connected inventory visibility (candidate)

The new read-only Inventory panel pages products, shows ledger-derived **available
quantity** (including negative values), and pages a minimal movement history. It
requires a freshly verified connected account with `inventory.read` and an
authorized workshop. Organization-wide selection uses the existing directory only
with `locations.read`. It does not open an offline baseline for inventory-only users.

Inventory is not cached or available offline. Stock and movement pages are separate
live reads with separate receipt times; one page is not a stock calculation or a
snapshot. Existing local operational drafts and journals remain available offline.
There is no product editor, movement command, inventory queue or quote UI in this
slice. See the [read contract and current qualification limits](docs/10-spec-development/2026-10-15-connected-inventory-read.md).

## V0.2 Increment 2 progress

Task 4 adds the [pure quote domain](docs/10-spec-development/2026-10-13-quote-domain.md):
integer-only labor/part/tax/discount calculations and immutable version history.
Quote persistence, authorization, API, sync and UI remain unimplemented.
Inventory API Task 3 was merged through PR #22 on 2026-10-14. See [Unreleased changes](CHANGELOG.md);
development versions and existing physical/manual release gates are unchanged.

## Principles

- Offline First and Local First
- Open Source First
- Modular monolith with explicit bounded contexts
- API First and vendor-neutral integrations
- Privacy and Security by Default
- WCAG 2.2 AA minimum target
- Right to Repair friendly
- White-label and implementer-friendly

## License

The Core and official applications are licensed under **GNU Affero General Public License v3.0 only (`AGPL-3.0-only`)**. See [`LICENSE`](LICENSE).

When users interact with the software over a network, deployments must preserve the corresponding-source obligations described by section 13 of the AGPL. The product UI will expose a visible Source Code link before V1.0.

## V0.1 implemented baseline

The current branch contains:

- FastAPI application shell with request IDs, JSON logging and health endpoints
- SQLAlchemy 2 models and Alembic migrations for tenants, customers, sync, outbox and jobs
- persistent users, Argon2 password hashing, signed/revocable sessions, real login endpoints and capability-based RBAC with deny-by-default behavior
- Customer REST API and deterministic OpenAPI contract
- TypeScript API types generated from OpenAPI plus a typed API client
- idempotent mutation ingestion, incremental change feed and explicit conflict results
- Transactional Outbox and durable PostgreSQL-oriented job queue using `FOR UPDATE SKIP LOCKED`
- filesystem BlobStorage adapter with content-addressed keys and traversal protection
- React + TypeScript + Vite PWA scaffold
- Dexie local database schema, durable mutation queue, sync cursor and Conflict Center persistence
- local-first Customer create flow, scoped SyncCoordinator, session-scoped auth cache, visible sync status and Conflict Center
- Docker Compose development topology for PostgreSQL 18.4, API and worker
- `ocwpctl doctor` and `ocwpctl status` baseline
- fixture sets for minimal, demo and load scenarios
- CI, DCO, REUSE/SPDX and security workflow definitions, including hosted Playwright + axe qualification
- PostgreSQL backup command wrapper that keeps passwords out of process arguments

## Verification in the current execution environment

Run the locally available V0.1 verification suite:

```bash
python scripts/ci/verify_v01.py --allow-blocked
```

The verifier distinguishes failures from environment-dependent blockers. Run it
in the current environment and inspect its exact-commit report rather than
assuming another machine's tools or evidence apply. Local PostgreSQL/Docker or
browser navigation may be unavailable; unit/static/build checks do not replace
those runtime gates. Hosted CI supplies PostgreSQL and production-PWA browser
qualification, while physical-device and operator reviews remain separate.

## Development commands

Backend tests:

```bash
PYTHONPATH=.:services/platform/src pytest -q
```

Frontend pure local-first tests without npm installation:

```bash
node apps/web/tools/run-core-tests.mjs
```

Fallback static TypeScript verification:

```bash
tsc -p apps/web/tsconfig.offline-check.json
```

Contract verification:

```bash
PYTHONPATH=services/platform/src python scripts/contracts/export_openapi.py --check
python scripts/contracts/generate_ts_client.py --check
```

When registry access is available:

```bash
corepack enable
pnpm install
pnpm --filter @ocwp/web build
```

Bootstrap the first administrator on a fresh migrated installation without exposing the password in process arguments:

```bash
printf '%s\n' 'replace-with-a-strong-password' > /tmp/ocwp-admin-password
chmod 600 /tmp/ocwp-admin-password
ocwpctl bootstrap admin \
  --organization-name 'Mi taller' \
  --location-name 'Sucursal principal' \
  --username admin \
  --display-name 'Administrador' \
  --password-file /tmp/ocwp-admin-password
rm /tmp/ocwp-admin-password
```

Hosted browser qualification is defined with Playwright and axe. It requires `OCWP_E2E_DATABASE_URL` pointing only to a dedicated local `_test` or `_e2e` PostgreSQL database before the destructive setup script may run.

When Docker is available, create `infra/compose/secrets/dev_auth_secret.txt` with a strong development secret and start:

```bash
docker compose -f infra/compose/docker-compose.dev.yml up --build
```

## Documentation

The normative design and execution specifications live under [`docs/`](docs/). Start with:

1. `docs/00-foundation/`
2. `docs/10-spec-development/open-cycling-workshop-platform-phase-10-spec-development-master-execution-system-v0.1.md`
3. `docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md`
4. `docs/10-spec-development/execution-state.yaml`
5. `MANUAL-ACTIONS-CHECKLIST.md`
6. `docs/superpowers/plans/2026-08-07-v0.1-bootstrap-customer-slice.md`

## Current blockers

The repository intentionally does not fake evidence for tools unavailable in the execution environment. `pnpm-lock.yaml` and `uv.lock` are generated by the hosted CI bootstrap when absent and published as the `v0.1-lockfiles` artifact before frozen installation. Docker/PostgreSQL smoke tests, browser IndexedDB tests, Android/Windows storage qualification and hosted security scans remain pending until their real runtimes execute.

## Local workshop MVP delivery

The laptop-to-ARM64 delivery sequence and acceptance criteria are tracked in
[the local workshop MVP plan](docs/10-spec-development/2026-10-14-local-workshop-mvp.md).
The additive [local runtime](docs/07-operations/2026-10-14-local-runtime.md) and
[recovery tools](docs/07-operations/2026-10-14-backup-restore.md) are implemented
and pending hosted qualification; existing development instructions are not a production installation
claim. Pending inventory/quote PRs are tracked separately from main. Physical-device
and manual release gates remain open.

### Personal presentation themes (implementation pending hosted qualification)

Personalización offers Banco de trabajo (default), Plano técnico, Ritmo modular
and Turno nocturno with shared operations, twelve palettes and touch controls.
Appearance is saved per user and organization on this browser/device. A PNG/JPEG
logo is an optional personal local view for the active location, available offline;
it does not change the identity seen by other users. Shared workshop branding
and cross-device preference synchronization are still pending. See the
[theme scope and evidence](docs/10-spec-development/2026-10-14-structural-workshop-themes.md).
