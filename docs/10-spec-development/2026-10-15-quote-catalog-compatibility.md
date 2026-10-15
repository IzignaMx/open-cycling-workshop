# Bounded quote catalog compatibility

## Specification before implementation

Base: `fe4db4ea56fd522cfa0152741918e85b0d9387a3` (actual main).
Scope: the capability prerequisite in the accepted
[quote persistence and online-command ADR §4](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md#4-explicit-quote-grants-and-old-client-compatibility).
Requirements: SEC-002/003; explicit scoped authority, old-client compatibility.
This slice was developed independently of the pure read-DTO prerequisite;
that prerequisite is now integrated from main46 as recorded below.

- Add a separate immutable three-literal `QUOTE_CAPABILITIES` set:
  `quotes.read`, `quotes.write`, `quotes.authorize`.
- The current catalog grows from 19 to 22 literals. Only the current Owner
  starter adds the three; all other current starter snapshots remain unchanged.
- Freeze the ten business capabilities, seventeen legacy wildcard grants,
  every legacy role bundle and v1 role alias. Role names are never authority.
- Preserve v2 catalog shape/version 2, `ocwp-access-baseline-2`, the epoch
  algorithm, context/transport shapes, existing read maps and all local schemas.
- Stored old accounts and tokens made through supported administration paths
  acquire no new quote authority. Name-only owner edits preserve grant list order
  and duplicates, scope and session version. Explicit owner creation, promotion
  or grant replacement requires all 22 grants and the actor's full delegation
  authority. Each quote literal remains independent; token/account intersection
  must include that explicit literal on both sides.
- A future explicit first-owner invocation creates the full current snapshot;
  legacy installation bootstrap still creates a location-scoped `*` account.
  Existing branding adoption still appends only its two branding literals.
- Re-export OpenAPI: only create/patch capability-list bounds change 19 → 22.
  Regenerate and check TypeScript, retaining its unchanged representational
  shape. Current generic administration can display the new literals from fresh
  v2 data; a stale nineteen-literal catalog refuses unknown-grant editing.

## Exact compatibility limitation

The guarantee covers snapshots produced through supported old grant APIs and
bootstrap paths. Those APIs reject unknown quote literals. A database operator
could nevertheless have manually preseeded one of the previously unknown
`quotes.read`, `quotes.write` or `quotes.authorize` literals in both a persisted
account and its signed token. That exact literal becomes recognized when present
in both snapshots after this catalog addition; `quotes.*` remains unrecognized. This slice does not
claim universal non-expansion for that unsupported preseeded state, introduce a
new protocol, rewrite stored snapshots, or silently adopt grants.

## Scope exclusions and evidence plan

Production implementation is restricted to `identity/roles.py`, plus generated
OpenAPI output. No routes, editor, migrations, adoption command, live account
changes, enrollment, operational quote activation or deployment. SQL remains
0012 and authenticated local schema 7. Mutation activation still requires every
accepted stage-3 fence, fresh-authority transaction and capacity/restore gate.

Use RED/GREEN tests for explicit quote recognition and current Owner catalog
membership, with exact frozen legacy snapshots, delegation and context/epoch
regressions. Qualify synthetic SQLite identity/CLI behavior and existing frontend
model/transport checks, lint, types, contracts and PWA build. No heavy maximum
capacity fixtures or local PostgreSQL qualification are included. Independent
source review is required before commit/publication. All hosted/native/physical
and operational gates retain their existing scope; local evidence does not
qualify them.

## Execution evidence

### Implemented boundary

Production changes are the separate immutable quote set, its current-catalog
union, and the Owner-only current starter union in `identity/roles.py`. The
existing concrete resolver, literal token/account intersection, fresh locked
actor checks and owner-preservation rules are unchanged. OpenAPI differs only
in the two create/patch capability-list `maxItems` values (19 → 22); regenerated
TypeScript is byte-identical. No routes are registered. SQL0012, authenticated
local schema 7 and all existing operational/read-map protocols remain unchanged.

Synthetic frontend coverage uses the existing runner and unchanged production
model/transport: a fresh 22-literal v2 catalog supports explicit quote grants,
a stale 19-literal catalog refuses unknown-grant editing, and name-only edits
send only expected version and changed name. Existing frontend validation
refuses duplicate stored grants rather than normalizing them; the API tests,
not frontend compatibility, establish exact duplicate/order preservation.

### TDD and retained failures

- The interrupted original RED log contains 33 failures / 17 passes.
- A fresh expanded RED run before production changes contains 36 failures /
  26 passes. After the minimal catalog change, all 62 cases pass.
- The explicit first-owner regression failed once against the unchanged
  nineteen-grant implementation, then passed with the exact 22-literal snapshot.
- The first full identity run retained one expected outdated-fixture failure:
  explicit successor Owner creation supplied the former 19-grant snapshot and
  correctly received `invalid_owner`/422 (593 passes, 156 explicit skips). The
  fixture now supplies all 22 literals, preserving the self-demotion/last-owner
  checks; non-owner denial also uses all 22 grants rather than a legacy role
  alias. Both focused tests and the final combined local rerun pass.
- Initial full mypy could not locate PIL through the older reused dependency
  environment. The unchanged check with the existing Python 3.13.5/Pillow 12.3.0
  environment passes all 111 source files. No dependency or type rule changed.
- `pnpm -r typecheck` attempted pnpm self-installation and failed creating its
  unavailable home store, before types or build ran. Repository-prescribed direct
  installed TypeScript/Vite invocations subsequently pass. No frozen install is
  claimed, and the initial failed attempt is retained.

### Available local evidence

- Quote identity compatibility: 62 passed; selected CLI modules: 31 passed,
  no skips. Synthetic SQLite only, one existing Starlette/httpx warning.
- Frontend focused checks: 54 passed. Final complete core runner on pinned
  Node 22.16.0: 912 passed, zero failures/skips; API-client core: one passed.
- OpenAPI export/check and TypeScript regeneration/check pass. Repository and
  contract tests: 27 passed. Direct repository validator passes.
- Full Ruff check and format (273 files), full ESLint, strict Python typing
  (111 source files), web/API/offline TypeScript checks pass.
- Current production PWA and the pinned legacy App/SW reproducibility build
  pass; legacy output contains seven hashed assets. The current build retains
  its existing >500 KiB chunk warning. No native browser execution is claimed.
- Final combined identity/ops/contracts/repository run: **704 passed, 156
  explicitly PostgreSQL/dialect-specific skips**, one existing warning. No
  failures or errors; skipped PostgreSQL/migration/lock behavior is unqualified.
- Full Prettier and final Ruff/ESLint checks pass. Synthetic SQLite HTTP smoke
  passes health, readiness, persisted login, mutation push and customer pull.
- Independent source review found no blocker: 158 focused identity/CLI passes,
  a separate 108 administration/adversarial passes and 59 frontend passes.
  External probes exercised every single omitted Owner grant across create,
  promotion and replacement with no rows/audit/version effects, cross-scope
  delegation refusals, near-match literals and 256 token/account combinations.
  Final documentation/evidence inspection is closed with no remaining blocker.
  The reviewer explicitly covers this metadata-only closure.

Independent review report SHA-256:
`02a437d50a5947fc51839c7551b7d6d66dc7923552b96e1033bfd6b3f8a0dd8f`.

Retained final Python log SHA-256:
`2161ae9607362339094494f3a2a4669a60de82bd1c5bd3b45d96506e5271a58c`.
Pinned-Node final core log SHA-256:
`66d3d57c456947cb0041b0291ff0b3b3913fffca2841d5ee7f81f47982ab5856`.
Fresh expanded RED log SHA-256:
`7a861ec21ee24b2b3eb197339c3c28238acb6df99eafa34fb2f514494063687e`.

All evidence uses existing local dependencies, including untracked dependency
symlinks excluded from source. Logs are retained in ignored `artifacts/` with
`quote-catalog-` names. No full aggregate, local PostgreSQL, heavy maximum
capacity fixture, hosted/native runtime or physical/operator qualification was
run for this bounded slice. Earlier hosted results do not qualify this new tree.
Publication, merge and deployment were not performed. The separate quote-only
operator adoption, protected read routes and every stage-3 activation gate remain
open.

## Reconciliation with merged pure read contracts

The normal integration joins PR47 head
`9d334b2ae3bc3be9159fa4438e90b6ceb697aec9` and actual main46
`c61e642d8e463e400a95e745556f659b69db8594` (tree
`5d3663c4ee88e78a3e2f20b0365c917348271a8e`). Only the changelog, manual
checklist and execution-state additions conflict; both histories are retained.
Every production, test and generated blob from either branch is unchanged.
The read-contract record now distinguishes its original no-catalog scope from
the combined tree's explicit catalog prerequisite. No application service or
quote route is introduced; old Owner19 still cannot delegate quote literals
without the separately authorized future adoption procedure.

Fresh local combined-tree evidence uses Python 3.13.5 and available Node 24.19.0.
Node results are local evidence, not pinned Node22 or hosted qualification.
Initial reuse of the older environment exposed eleven dependency-security
failures (1,820 passes, eight skips, 477 deselected); isolated reproduction
confirmed outdated PyJWT 2.13.0 behavior (reused Starlette 0.52.1). A separate worktree-local frozen uv sync with
all workspace packages supplies the actual committed dependency lock. The initial
root-only sync did not install workspace application dependencies. No source,
security policy, test or dependency lock was changed to address these failures.
Initial frontend attempts exposed stale workspace links and missing fake-IDB;
local dependency links and the pinned fake-indexeddb 6.2.5 registry package
corrected the environment without source edits. Missing PIL initially blocked
mypy; Pillow 12.3.0 resolved it. Those failures remain retained in local logs.

- Frozen all-workspace Python rerun: **1,831 passed, eight skipped, 477
  deselected**, one existing Starlette/httpx deprecation warning. Three skips
  require real PostgreSQL and five require the hosted scanner. Deselected cases
  are not passes. Locked PyJWT 2.15.1 and Starlette 1.3.1 resolve all eleven
  initial environment failures without source changes.
- Complete frontend core: 912 passed, zero failures/skips; API-client core: one
  passed. Web, API-client and offline TypeScript checks pass.
- Full Ruff check/format (275 files), mypy (112 source files), ESLint, repository
  validation, generated OpenAPI/TypeScript checks and full Prettier pass.
- Current production PWA builds with its existing large-chunk warning. Native
  browser execution and the pinned legacy build are not rerun here.
- Independent source/union review found no production blocker; its focused
  combined suite passed 129 cases with 65 explicit PostgreSQL-unconfigured skips.

The existing single 16 MiB serializer-boundary test is included in the combined
Python selection; it is not maximum-history capacity or PostgreSQL qualification.
No full aggregate, native browser, live account/token/adoption, migration,
capacity experiment, installation or deployment is performed. Previous hosted
results remain tied to their original source. Exact-candidate hosted qualification
and main46 postmerge acceptance remain external gates; no merge readiness is
inferred from this local reconciliation.
