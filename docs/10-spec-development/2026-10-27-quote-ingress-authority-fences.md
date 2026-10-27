# Quote ingress and authority fences · 2026-10-27

Status: implemented pending exact-source hosted evidence; independent final review
passed. Base main is `a9e161f7fdcb986828f85a59c46a5a47015c7b34`.
[Its postmerge qualification](2026-10-27-pr59-postmerge-reconciliation.md) is not
inherited by this source. This is a bounded prerequisite within Tasks 5/8, not
completion of either task or activation of quote routes.

## Requirements and implementation boundary

Implements the accepted [online-command ADR §§4 and 7](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md),
with the [bounded-effects amendment](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md)
and [semantic closure](2026-10-17-quote-semantic-closure.md).
Traceability: FR-SVC-007/008/009/011 and FR-INV-003/004; deny-by-default scoped
capabilities, durable receipt idempotency and preservation of immutable history.
No new architecture, storage schema or grant-resolution policy is introduced.

- Legacy writers keep the organization → fresh actor → scoped order → lineage
  ordering; order-linked inventory takes its product lock afterwards. The existing
  organization barrier serializes even the absent-lineage case with enrollment.
  A shared scalar-only guard reads location and lineage identity before mapped
  order Text hydration. Permitted order loads refresh after acquiring the lock.
- HTTP transitions and sync updates refuse every generic non-cancellation action
  on a quote-managed order. Membership never depends on quote grants, current
  decision state or successful reconstruction; malformed retained history cannot
  restore a legacy bypass. Existing lawful cancellation retains its state machine
  and history. Sync refusal remains an explicit conflict, not an offline approval.
- New order-linked inventory movements are refused for enrolled orders. Existing
  exact historical inventory receipt replay remains a no-new-effects path after
  fresh ordinary authority and product/idempotency checks. The scoped scalar fence
  precedes the product lock; unrelated legacy orders keep their existing behavior.
- `access adopt-quotes` explicitly targets one active established organization-wide
  owner using an expected user version. It requires current schema 0013, the
  generated-count definitions and quote model shapes; it neither migrates nor
  reconstructs/repairs retained history. Organization and fresh owner locks, known
  grant validation and CAS precede mutation. Only missing literal `quotes.read`,
  `quotes.write`, `quotes.authorize` grants are appended. Existing list order,
  duplicates, wildcard, scope, password and unrelated attributes remain unchanged.
  A change increments user/session versions and appends identity audit atomically;
  an already-complete adoption is a no-op after validation and CAS.

The CLI implementation is exercised only on synthetic accounts in this work;
it is not permission to adopt any real account. Explicit database configuration
is required. No startup/migration adoption, all-owner bulk adoption, catalog/role
expansion, legacy wildcard reinterpretation or cutover-floor mutation is added.
The existing fresh-authority intersection remains the upper bound on writers.

Guarded writers require the current migrated quote schema even when an order has
no lineage; an absent quote table never falls back to legacy permission. Installing
this binary against an old schema or alongside mixed old writers is neither
authorized nor qualified here. These dependencies are fail-closed operational
prerequisites, not rollout readiness evidence.

## Evidence boundary and next gates

The adoption command was observed failing on the old unsupported-command path
before implementation. Final focused adoption/schema tests passed **24** with
**2 local PostgreSQL-environment skips**. The overlapping broader adoption,
unchanged branding, first-owner and quote-catalog regression selection passed
**114** with the same **2 local skips**; these counts are separate scopes, not
additive totals. Ruff/format and strict mypy for the two adoption production roots
passed. No actual account was changed.

Ingress TDD first observed **20 failures / 2 passes** on old behavior; the final
expanded focused selection passed **35**. It covers three actual HTTP paths,
mixed sync batches, wildcard/no-quote-grant callers, all four inventory-kind exact
receipts, sync receipt replay, refusal before Text hydration, unrelated ADJUST,
stale ORM refresh and enrollment rollback. The overlapping broader affected
selection passed **1,023** with **69 local PostgreSQL-environment skips**, not the
hosted suite's 58 intentional skips. Do not add these overlapping counts.

The final affected selection (quotes, service orders, sync, inventory and the new
adoption files) passed **1,965** with **468 local environment skips**, 10 warnings,
in 125.56 seconds; no failures. Repository/serial-shard contracts separately passed
**110** in 3.56 seconds. Local skips disclose unavailable runtime environments;
they are not the hosted suite's 58 expected-skip acceptance set. Earlier selections
above remain overlapping diagnostic scopes, not additional passes to sum.

Whole-production mypy (**121** source files), OpenAPI/generated TypeScript checks,
Ruff and formatting (**318** files) passed. Independent final review found no
blocking issues; its combined selection passed **59** with **8 local PostgreSQL
skips** in 8.30 seconds. Full collection is **4,794**: the prior 4,727 plus **67**
new cases. Eight new actual-PostgreSQL cases await hosted execution: six ingress
races and two adoption CAS/rollback cases. Collection and SQLite do not prove
lock ordering, waiting revocation or enrollment races.

Local frontend smoke passed **934 web-core + 1 API-core** cases with zero skips;
web/API TypeScript checks and whole-repository Prettier passed. Frozen dependency
installation changed no lockfile. Local Node 24.22.1/pnpm 11.25.0 are distinct
from hosted Node 22.16/pnpm 11.17; these results do not establish the hosted PWA
build or native browser/IndexedDB acceptance.

Before accepting this slice: complete exact-source hosted PostgreSQL races and
the full existing CI ladder,
including exhaustive collection, 58 expected skips, six restores, both owned
cleanup proofs and direct/aggregate retry-free browser evidence. Retain failed
results and diagnose source errors; no identical-head blind retry or resource
change. Record exact candidate and artifacts when available.

No quote HTTP routes, API schemas, generated contract changes or UI are introduced.
Transport/cancellation and total Python deadline guarantees, product capacity/
latency, mixed-old-writer adoption, physical R01-T035 Windows/Android/laptop/Pi,
manual accessibility and real-volume recovery remain separate gates. No real
adoption, installation, deployment, reopening or capacity trial occurs. A fresh
PR remains draft; merge requires specific approval. All inherited time/resource,
collection/skip/restore, cancellation and cleanup bounds remain unchanged.
