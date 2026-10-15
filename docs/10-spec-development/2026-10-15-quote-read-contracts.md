# Quote revision read contracts · bounded unmounted slice

## Specification before implementation

Base: `fe4db4ea56fd522cfa0152741918e85b0d9387a3`. Implements only the pure
projection/closed DTO part of accepted quote persistence ADR stage 2, tracing
FR-SVC-005/007/008/009/016, BR-004/005/006/007, SEC-002/003 and NFR-009.

- Input is the complete `QuoteSnapshot` returned by `QuoteRepository.load`
  after strict reconstruction of every financial revision, decision, operation
  and outbox receipt. Projectors are not a persistence validator or an authority
  token issuer. A manually assembled snapshot is not admissible application input.
- The existing repository load enforces transaction-owned writer admission and
  order → lineage locks after the `lock_writer` organization → fresh actor barrier.
  Future application reads must select protocol 1, use the already-narrowed
  incoming principal, require both `quotes.read` and `orders.read`, refresh
  authority after waits and recheck expiry after projection. New source-path
  tests select protocol 1; they do not add grant checks to the repository.
  This original slice provided no application service or quote grants. The
  subsequent catalog prerequisite recognizes three explicit quote literals;
  the combined tree still provides no quote application service or routes.
- Revision metadata pages are ascending version order, default/max 25. Full
  history validation precedes pagination. No list of complete revisions is exposed.
  Continuations are opaque deterministic SHA-256 position fingerprints bound to
  organization, location, order, lineage and current head/decision sequence.
  They contain no raw scope/proof and grant no authority. They are not signed
  authorization credentials. Any changed lineage cursor requires restarting the
  page sequence; a fresh complete admitted read is required for each page.
- Revision detail contains immutable identity, version, creation time,
  predecessor, currency, original typed line presentation order and exact totals.
  Derived supersession fields and current decisions do not enter the immutable
  revision payload. A separate `current` context identifies scope, lineage,
  current head/version and decision sequence. It does not authorize execution.
- Closed, frozen DTOs reject unknown fields and numeric coercion; returned money
  and versions are exact safe JSON integers, including signed discount line
  amounts. IDs, canonical microsecond UTC times, currency, text, line/target
  counts retain the accepted storage bounds. No raw proof, decision evidence,
  notes, source references, operation receipts or full order payload is returned.
- A dedicated serializer bounds the exact UTF-8 JSON bytes to 1 MiB. Read failures
  use one closed allowlisted code with no input/exception echo, at most 8 KiB.
  This is not HTTP error handling: middleware, private no-store/correlation
  headers, request guards, OpenAPI and generated clients remain a later slice.

## Verification plan and exclusions

Use small synthetic histories only. Observe red before implementing projection.
Prove DTO shape/numeric/text boundaries, all four line kinds, signed discounts,
metadata pagination, scope/stale/malformed continuation refusals, immutable old
revision detail with fresh lineage context, exact serialization byte limits and
privacy-safe bounded errors. Source-path tests must use the real repository load
and detect corruption outside the requested page/detail, stale or absent
transaction admission, and foreign scope before projecting any result.

No routes, app registration, catalog/grants, migrations, UI, production
activation, heavy capacity fixture, PostgreSQL run or benchmark. Task 6 maximum
capacity remains unqualified: the separately retained 111-operation/~8.4 MB
cumulative preflight failed and the guard review remains held. These small tests
cannot qualify that gate. Exact-source hosted checks remain pending; no publication, merge or deploy is authorized by this slice.

## Evidence

- Missing `cycling_workshop.quotes.reads` was observed red before implementation.
- DTO identifier U+0000 rejection was observed red and fixed before the final run.
  An initial corruption-injection test used the wrong outbox table name; it failed
  in fixture SQL, was corrected to the registered `outbox_events` table, and rerun.
- Final small-fixture source suite: **581 passed, 255 deliberately deselected**,
  covering all quote tests plus order state-machine and inventory domain tests
  except PostgreSQL cases and the pre-existing 16 MiB budget specimen. This
  includes **67 new read-contract cases**. No deselected case is a pass.
- Repository/migration-string contracts: **23 passed**.
- All quote source/tests: Ruff check and format check passed (22 files); strict
  mypy passed for all 10 quote source files. `git diff --check` passed.
- Commands used the existing locked Python 3.13.5 virtual environment without a
  dependency change. This slice does not rerun the full aggregate, PostgreSQL,
  browser, generated-client or capacity qualification.
- Independent source review found no remaining blocker for this pure unmounted
  scope. Seven additional small independent cases passed (seven PostgreSQL
  variants deselected), covering all numeric positions, signed safe-integer
  minimum, Unicode, empty arrays, nested validation bypasses and scoped cursors.
  The reviewer identified a nonblocking weak foreign-cursor test; the committed
  test now proves valid continuation positions in both scopes before testing
  mutual reuse and tampering, and passed the reviewer's independent rerun.
- Reviewed source SHA-256:
  `1e2780d1c8613ef65a119a7477ba811ba843601b815419566265a7f14f734db8`.
  Final tests SHA-256:
  `4e37af395a2359c7c67127058925319011d3c97e8681fd51843239445a6c9aae`.
  Independent review report SHA-256:
  `42f1af8350dae88c8ce76cea647337ca6270fffead2591ef5f5a05549228168c`.
- No application service, HTTP route, UI journey, new grants or production
  readiness is claimed. Exact-source hosted qualification remains pending.
