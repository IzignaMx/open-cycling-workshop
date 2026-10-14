# Isolated server-context adapter increment

Status: implemented and locally unit-tested; unactivated prerequisite.

## Scope and acceptance

See the [ADR and integration contract](../02-technical-architecture/2026-10-14-isolated-server-context-adapter.md).
Only the new adapter, its test file, test-runner registration and documentation
change. Backend, generated OpenAPI/client contracts, production App/auth/defaultDB,
all persistent schemas and existing browser tests remain unchanged.

- Capture immutable request principal/location/session/generation/token and realm.
- Bind server null realm to the checked configured API destination.
- Reject redirects and unsafe cache/response contracts without leaking failures.
- Validate exact current wire fields and signed-expiry-bounded UTC lease.
- Preserve literal concrete grants; reject principal/scope/epoch inconsistencies.
- Reject late requests, session/token replacement, generation/tab changes and
  invalidation both during fetch and body resolution.
- Always return BASELINE_REQUIRED; no activation or baseline ingestion exists.

## Evidence and limits

Initial test failed because the adapter module was absent, before implementation.
58 isolated injected-fetch/clock tests pass. Full frontend core suite passes
216 tests with zero skips, preserving all 158 earlier tests. Kernel TypeScript
compilation and touched-scope ESLint pass. The normal core runner also compiles
the existing isolated browser harness without changing its cases.

Injected fetch tests establish request options and stale-response handling;
they are not native-browser redirect, service-worker or real HTTP evidence.
No new native-browser run, PostgreSQL run, fresh dependency installation,
server deployment or production integration is claimed. Independent review found no blocking issues and independently reran kernel
TypeScript compilation and all 58 adapter tests after the final code change.
The exact commit/tree and validation are recorded in the parent publication manifest.

## Changelog and operational status

Add an isolated transport prerequisite for the authenticated context endpoint.
There are no new operator secrets, migrations or account changes. No manual
release gate is closed. Existing Windows/Android physical, accessibility,
authoritative baseline consumption/activation, old-writer cutover, restore and
non-destructive legacy recovery work remains pending as applicable in the manual
checklist. Preserve original realm journals on API moves; never retarget them.
