# Open Cycling Workshop Platform

Open source, local-first, offline-first operating platform for bicycle workshops, stores, cooperatives, fleets, and cycling-related service organizations.

> Status: **V0.1 Foundations / hosted CI + Security green · Compose fresh-install, backup/restore drill and IndexedDB 100k benchmark proven · remaining: physical device qualification, conflict-path browser evidence and chaos gates**. This repository is not yet a production release.

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

The verifier distinguishes failures from environment-dependent blockers. In this execution environment the Python suite, real Uvicorn HTTP smoke, TypeScript core tests, generated API client tests, fallback frontend typecheck, repository contract and OpenAPI drift checks can run. Docker, PostgreSQL, the npm registry, Ruff, mypy and browser navigation are unavailable or policy-blocked here, so their gates intentionally remain incomplete.

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
