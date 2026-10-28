# OCW modularity strategy — source-bound design review

Baseline reviewed: `a960bddb94189c6c74c7f3d0a72472636c3caced`. This is a recommendation for spec-development, not a runtime certification, deployment, grant, or installed extension. All source references below are relative to https://github.com/IzignaMx/open-cycling-workshop/tree/a960bdd.

## Executive finding

OCW is a modular application with explicit composition, **not an implemented extensible plugin platform**. Safest and cheapest path: formalize reviewed build-time official modules first; independently qualify external process/API connectors later. Do not add a dynamic Python loader, npm remote modules, arbitrary JS, marketplace installer, or database plugin hooks now. Capability requests and manifest validation must never confer authority.

This implements the intent already specified in phase 5 §18, phase 8 §§51–82 and phase 10 §33, rather than introducing competing policy. Link early prerequisite work to existing `R09-T020` (SDK/compatibility kit) and `R10-T014` (SDK qualification), without declaring those complete.

## What exists, with evidence

- `packages/plugin-sdk/src/index.ts`: `export {}` with explicit no-runtime comment; package private, version `0.1.0-dev.0`. There is no public SDK implementation to promise today.
- `services/platform/src/cycling_workshop/app.py`: explicit imports and `include_router` composition. `db/registry.py`: explicit imports of ORM models. `apps/web/src/App.tsx`: direct React feature/controller imports. These are practical build-time extension seams, not discovery/installation hooks.
- `packages/api-client/openapi.json`, `src/generated.ts`, `src/client.ts`: existing wire/client foundation. Only mounted, supported API operations qualify as potential connector surfaces; internal domain functions do not. In particular quote domain/persistence exists but no quote router is mounted in baseline `app.py`.
- `identity/dependencies.py`: bearer human session validation, current account/grant intersection, organization compatibility/incarnation checks. No dedicated external connector identity protocol is implemented here.
- `identity/roles.py` and `apps/web/src/auth/capabilities.ts`: legacy wildcard capability snapshot deliberately frozen; new quote/branding grants explicit. Adding a module must not expand old `*`, old role snapshots, or existing accounts.
- `tenancy/models.py`: organization/location model, dataset incarnation and minimum write protocol. These are real scope fences, not automatic proof every extension respects them.
- `apps/web/src/access-kernel/types.ts`: principal realm/org/user, selected location, epoch, policy revision, dataset incarnation and offline expiry. `apps/web/src/sync/types.ts`: closed operational entity types customer/bicycle/service_order. No generic plugin sync registration.
- Inventory feature/server READMEs: online-only scoped reads, no feature-owned auth/IndexedDB/write queue; frontend stale account/scope generation fences; server read locks, bounded queries, minimal projection and no-store. Preserve those rather than bolt a generic fetch onto a panel.
- `events/outbox.py`: internal transactional event enqueue; `worker.py` main starts with empty handler mapping. Neither proves exported stable event schemas, subscriptions, connector transport, replay/ack protocol or delivery authorization.
- `services/platform/migrations/versions/0001...0013`: existing centrally reviewed Alembic lineage, not a plugin migration engine.
- Phase 8 specifies AGPL official policy, reviewed external connectors, namespace ownership, permissions, installation lifecycle and Git-backed registry, mostly future design. Phase 5 manifest uses `platform/capabilities/subscriptions`; phase 8 uses `schema/core.requires/permissions/events.subscribes`. **Resolve that draft vocabulary divergence before creating a normative schema.** No already-published runtime manifest compatibility is evidenced by the empty SDK.

## Alternatives

| Approach                                                                                                  | Cost / value                                                                                                                                                     | Decision                                                                                         |
| --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Reviewed official modules compiled/released with backend and PWA; explicit imports and typed ports        | Least architectural change; leverages CI and existing source review; coordinated release; not fault/security isolation from trusted core                         | Adopt now, preserve explicit registration. Optional feature enablement is not authorization.     |
| Independently deployed connector using narrow authenticated HTTP/events, separate process and own storage | Language independence, failure containment, release independence; requires service identity, rate limits, lifecycle, delivery contract and operational isolation | Adopt staged after contracts and security gates. Start online read-only; no core DB credentials. |
| Dynamic in-process third-party Python/JS plugin framework (or remote frontend code)                       | Highest blast radius; bypasses source-reviewed auth/storage/offline assumptions; complex ABI/migrations/dependency risks; sandbox not implied by manifest        | Reject for this phase. No need for WASM/iframe platform before a concrete justified use case.    |

A process/container boundary alone is **not** a full sandbox. Qualification must prove no inherited core secrets, host/Docker socket/core-volume mounts or database credentials; separate identity, resource/time limits and enforceable egress policy. Third-party remote UI remains out of scope; host-rendered declarative data or separate application links are safer initial surfaces.

## Normative contract proposal (not installed runtime)

Keep one `manifest schema version`, separate from module package SemVer, host/Core version, HTTP API major, event schema major, data schema revision and offline protocol. Use phase-8 canonical concepts (`schema`, `core.requires`, `permissions`, `events`) and document phase-5 draft aliases as superseded, not silently accepted fields. In pre-1.0 qualify explicit tested host builds/ranges; do not imply `>=1.0 <2.0` works on today's dev build. Python package version spelling is not automatically npm SemVer; host compatibility identity must be explicit and testable.

Proposed closed fields: immutable reverse-DNS `id`; `name`; `version`; SPDX `license`; source URL and immutable revision; maintainer/security contact; `core.requires`; `api.requires`; `runtime.type` (`official-build` or `external-connector`); requested `permissions`; permitted UI slot IDs; declared event names/versions; `network.hosts`; secret **names/purposes only**; data categories/namespace/retention/export policy; `offline.mode` (`online-only` initially); lifecycle/health contract version; declared data migrations (ID/from/to/checksum/rollback safety); compatibility evidence references. Bounds on string/list size, strict parsing, duplicate IDs rejection, unknown fields/capabilities rejection. No executable hook strings, Python import paths, shell commands, embedded credentials, or code URLs loaded by validation.

Artifact digest/provenance and `Official/Verified` assessment belong to trusted release/registry records; author self-assertion is not certification. A valid manifest is a descriptor, not approval, installation, credential issuance or enablement. Begin with minimal required subset plus explicit no-data/no-events/no-secrets empty declarations; don't build an installer just to validate a manifest.

### Official module boundary

Explicit reviewed composition imports/routes/models; typed DTO/application-service ports across domains, no neighboring repository/table writes. Any build registry is a source-owned allowlist, never sourced from untrusted manifests. Existing module extraction must be behavior-preserving and separately tested; do not rewrite app composition as prerequisite to documentation/manifest validation. Core auth and tenancy stay centralized. Official UI uses existing tokens, navigation, accessibility, unsent-form preservation and session generation checks. No core authority or offline kernel objects in a public extension interface.

### External connector authority and data

Future dedicated revocable service identity scoped to installation + organization + allowed locations + explicit capability set, with expiry/rotation/audit; never reuse owner wildcard/session credentials or mint tokens in sample scaffolds. Effective permissions are intersection of current installed grants, identity/token limits and endpoint policy, rechecked per request. Server derives/verifies tenant scope rather than trusting manifest/body IDs. Revocation cancels delivery and blocks retries; new grants/egress destinations require explicit approval, no automatic upgrade expansion.

Core owns authoritative customers/orders/inventory; connector owns only named local projections/config/delivery receipts. No SQL access, cross-namespace writes or blind full-row exports. Minimize event payloads; authorize hydration/read separately. Export, disable, revoke, uninstall-retain, and separately confirmed purge are distinct. Disable cannot delete core data; uninstall revokes secrets while preserving documented export/retention path.

### Delivery, commands and offline

Future events need unique ID, type/schema version, aggregate ID/version, occurred time, authorized scope and minimal payload; mapping/redaction adapter between internal outbox and public event contract. At-least-once delivery, scoped durable dedupe, bounded retry/backoff/dead-letter/replay and explicit ordering guarantees (not implied global exactly-once). Transactional outbox handoff must not block domain transactions on network calls. Receiver acknowledges only after durable receipt.

Future commands: scoped idempotency key + canonical request fingerprint, atomic receipt/effects; exact replay returns original accepted result; same key/different intent rejects. Permission loss and dataset-incarnation change must not permit a replay to create new effects. Test crash after effect/before acknowledgement and retention boundary explicitly.

Default connectors and first official example **online-only**. Declaring offline support does not enroll an entity in sync. Offline additions require separate ADR, entity/version/conflict schemas, baseline and pull/push compatibility, tenant/principal/epoch/incarnation partitioning, lease/expiry/revocation behavior, stale A→B→A response rejection and migration/recovery tests. Disconnected UI is honest unavailable, not authoritative stale inventory or queued privileged action. Connector failures must not block login, opening an order, stock ledger integrity or local capture.

### Migrations and compatibility

Official models use reviewed central Alembic graph; no independently auto-run plugin migrations into core tables. Require preflight, backup/restore evidence where material, forward-compatible expand/contract plan, upgrade from supported prior revision and interruption recovery. Alembic migrations run once by revision; do not inaccurately require every SQL statement to be idempotent. Retry-safe migrations/reconciliation need explicit preconditions, recorded status and safe restart. Rollback is permitted only when data-safe; otherwise restore/forward-fix plan, no automatic destructive downgrade. External connector owns and migrates its separate store.

Breaking public contract changes bump relevant major and provide migration guide/deprecation window; additive change still tested against closed DTO validators (not automatically safe). Publish a matrix host build/API/schema/module version → test result, not a broad compatibility badge without evidence. Reject unsupported combinations before enablement; no silent downgrade of permissions or protocol floors.

## Incremental implementation plan and evidence

**M0 — Immediate bounded slice:** ADR + status matrix; canonical manifest design/schema, pure validator, valid and invalid fixtures, contract-only starter and author guide; wire focused validator checks into existing CI with no service credentials/network/install side effects. Explicitly no runtime SDK, auth changes, new tables, migrations, sync protocol, grants, deploy or marketplace. Acceptance: malformed/unknown/duplicate/oversized/incompatible manifests fail, capability requests do not modify existing grants, schema/examples/docs agree. A strict test of unsupported version representation is important.

**M1 — Official reference:** source-reviewed online read-only feature (e.g. existing inventory read projection rendered using existing transport and authority facade, or inert module-information component without data access); explicit build composition. Prefer reuse over a generic plugin loader. Validate disabled/unavailable/error state leaves ordinary order capture intact, no new storage/auth/queue; add accessibility/theme/unsent-form and stale-response tests. Host-only metadata example is lowest-risk starter; do not brand a mock inventory connector production-ready.

**M2 — Connector boundary:** dedicated machine identity and revoke/rotation audit; bounded one-resource read facade; separately launched example with own store, no default enablement, no real data. Negative two-tenant/two-location tests, expiration, current-grant reduction, replay, policy escalation, privacy/no-store, resource exhaustion/crash/offline prove isolation. This is a separate security-sensitive spec/review, not incidental M0 scope.

**M3 — Events and opt-in writes:** versioned minimal public events + outbox adapter/delivery; dedupe/replay/dead-letter; then one narrowly authorized idempotent command. Establish crash/timeout/restart reconciliation and data export/uninstall evidence before broader adapters (payments/tax/hardware/communications). No direct inventory adjustment until ledger admission/receipt invariants remain proven.

**M4 — SDK/registry qualification:** executable compatibility kit, documented supported version matrix, provenance/SBOM and trusted Git-backed records, lifecycle/security review, real supported-environment evidence. Only then mark relevant R09/R10 gates complete; installation/deployment remains separate authorization.

Author guide should walk: choose official vs external → name/scope/ownership → manifest → typed API ports → explicit permissions and no authority side effects → tests → compatibility/license/source notices → reviewed PR → release/disable/export/recovery. Provide executable starter command and expected output only once implemented. Existing governance requires DCO/review; do not assert current repository protections enforce every aspirational governance rule.

## Minimum acceptance checklist

1. No new authority from manifest/feature toggle/catalog or historical wildcard; unchanged grants and core app route/storage snapshots in M0.
2. Reject unsupported host/API/schema and unknown requested capability; schema is single source of truth, no draft aliases ambiguity.
3. Cross-tenant/location, token expiry, revocation, epoch/incarnation and stale-response refusal tested at actual boundary.
4. Connector lacks database/core secret/host access; process death/timeout leaves core working; quotas and egress enforced, not merely documented.
5. Duplicate event/command, reordering, lost acknowledgement and crash recovery are deterministic; replay never duplicates stock or financial effects.
6. Migration compatibility, restore/forward-fix and disable/export/uninstall preservation proven with actual database where claimed; skipped PostgreSQL/browser tests are not qualification.
7. Private responses/logs and event data minimization match existing inventory/quote privacy contracts; no tokens/PII in docs/screenshots/examples.
8. Public status labels distinguish designed, implemented, locally tested, qualified, activated. SDK/registry/install capability must not be advertised from empty package plus specifications.

## Risks needing visible tracking

Security false confidence from manifest/container; accidental grant widening; exposing internal outbox/domain data as API; sync schema expansion corrupting tenant-local work; optional module migrations making core startup fragile; registry trust self-certification; unsupported SemVer prerelease comparison; licensing overclaims. Preserve `AGPL-3.0-only` project policy for official code/SDK/examples. External process separation alone is not a universal legal conclusion about derivative works; document license and use project review for legal exceptions, with no promised automatic exemption.

## Integration into the active action plan

This is an assistant-selected strategy under the maintainer's technical
delegation, not a claim of human review or completed SDK. The current public
presentation increment delivers truthful onboarding and describes these gates.
Next independent M0 work is a strict data-only canonical manifest schema, pure
validator, negative/positive fixtures, contract-only starter and guide. Resolve
the Phase 5/8 vocabulary disagreement explicitly before implementation; no
automatic credentials, runtime loading, migrations or capability grants.

M0 is a prerequisite contribution to R09-T020 and R10-T014, not completion of
those future SDK tasks. Later official read-only reference integration and
external connector/service-identity work require their own source-bound plans
and acceptance. The existing streaming/cancellation, capacity, installation and
physical gates retain priority; no consumed capacity trial is re-executed.
