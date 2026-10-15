# Bounded quote catalog compatibility

## Specification before implementation

Base: `fe4db4ea56fd522cfa0152741918e85b0d9387a3` (actual main).
Scope: the capability prerequisite in the accepted
[quote persistence and online-command ADR §4](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md#4-explicit-quote-grants-and-old-client-compatibility).
Requirements: SEC-002/003; explicit scoped authority, old-client compatibility.
This slice is independent of the unmerged pure read-DTO draft.

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
