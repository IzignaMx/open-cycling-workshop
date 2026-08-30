# Architecture

The authoritative architecture is documented under `docs/02-technical-architecture/` and `docs/05-engineering/`.

## Baseline

- modular monolith
- React + TypeScript + Vite PWA
- Dexie / IndexedDB local persistence
- Python + FastAPI + Pydantic + SQLAlchemy 2 + Alembic
- PostgreSQL authoritative server persistence
- UUIDv7-compatible IDs
- idempotent mutation log + incremental change feed
- Transactional Outbox
- capability-based RBAC, deny by default
- Docker Compose deployment baseline

The Core does not depend on WhatsApp, a payment provider, an AI service, a proprietary cloud, or any other optional external service.
