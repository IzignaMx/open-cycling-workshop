# Quote request decoding · inactive input boundary

## Scope

This independently reviewable increment follows the accepted
[quote persistence/online ADR §5](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md#5-bounded-persistence-and-rest-contract)
on main `fe4db4ea56fd522cfa0152741918e85b0d9387a3`. It adds only pure input
values and decoders in `quotes/requests.py`; it does not activate an HTTP route,
application service, grant, adoption, enrollment, database change or offline API.
Pure domain constructors and storage reconstruction remain unchanged.

Requirements touched: exact financial inputs, bounded hostile JSON, immutable
consent provenance and server-owned authority from ADR §§5.1–5.2. This is local
input-shape evidence, not completion of Task 6 or stage-3 activation.

## Closed contracts

Every listed member is required. Nullable evidence text must be explicitly null
when absent. Unknown members are refused, including inside each line/evidence.
Decoded frozen values are **not authorization or fully admitted domain commands**;
constructing a dataclass directly is not the decoding boundary.

- Create: `kind="create"`, `operation_id`, `quote_id`,
  `expected_order_version`, `currency`, `lines`.
  The repository create command already derives absent head/sequence as null/0/0;
  clients cannot override those facts.
- Revise: `kind="revise"`, `operation_id`, new `quote_id`,
  `expected_order_version`, `lineage_id`, `expected_head_id`,
  `expected_head_version`, `expected_decision_sequence`, complete `lines`.
  Currency is not supplied; the later service obtains the lineage currency.
- Initial decision: `decision_id`, `expected_order_version`, `lineage_id`,
  `expected_head_id`, `expected_head_version`, `expected_decision_sequence`,
  `evidence`. The existing repository uses decision ID as operation ID.
  Only the separately supplied `authorize-partial` action admits the additional
  required `approved_line_ids` list. `authorize` derives all charge IDs from the
  locked revision later; `reject` selects none. The decoder does not authorize
  its caller, and a later router must bind this argument to its actual route.
  The route revision ID is not accepted from the body.
- Evidence: `party_kind="customer"`, `party_id`, `channel`, `decided_at`,
  nullable `source_reference`, nullable `note`. Allowed channels are in_person,
  phone, email, messaging and written. No representative or portal provenance,
  corrections, withdrawals, server recording reason/time/actor, body outcome,
  prices or totals are accepted. Rejection explanation can be evidence `note`;
  the separate recording/correction `reason` contract remains deferred.
- Lines reuse the existing closed storage line members for labor, part, tax and
  discount. Description raw bounds are checked before whitespace normalization;
  targets are sorted before the canonical codec, which still refuses duplicate
  targets. Presentation line order is retained. At least one charge, unique line
  IDs, 100 total lines, 1,000 target edges and existing scalar bounds are required.

New IDs are canonical UUIDv7. Existing customer/product references retain the
existing 1–36-character, non-whitespace ID compatibility, **without a scoped
lookup claim**. Times use explicit RFC3339 syntax with at most six fractional
places and known offsets, normalize to UTC and never round. Unknown-offset
`-00:00`, leap seconds unsupported by Python datetime, impossible dates and UTC
normalization overflow are refused. Text is globally checked for NUL/surrogates
and field-specific codepoint/UTF-8 bounds; nothing is truncated.

## Bounded decoding and deferred integration

`decode_request_document` consumes a synchronous iterable of actual byte chunks
into one bounded bytearray, checking cumulative bytes before each append. It
refuses byte 131,073 before JSON parsing and never trusts Content-Length. Empty
chunks do not accumulate objects. UTF-8 is decoded strictly after collection, so
split multibyte characters work. A string/escape-aware pre-scan refuses container
depth over 12 before the standard JSON parser. JSON hooks refuse duplicate keys
(including escaped aliases), floats/exponents, nonfinite values and integer
lexemes outside ±(2^53−1) before integer construction. JSON integer `-0` is
accepted as exact zero; it cannot bypass positive-version/minimum checks. Global exact-value checking
also covers keys. UTF-8 BOMs and malformed JSON are refused.

Only absent or identity content encoding is admitted; compressed encodings are
refused before iteration. **This module does not read headers or ASGI streams.**
The eventual HTTP wrapper must inspect Content-Encoding itself, pass/validate its
value before reading, bound actual asynchronous chunks before buffering or
parsing, handle disconnect/cancellation, bind path/action, and apply no-store and
server-generated correlation IDs to every success/error. A synchronous decoder
does not prove chunked HTTP enforcement. Fixed `invalid_request`, `too_large` and
`unsupported_encoding` errors contain no input, field names or evidence and are
far below the 8 KiB error budget; no HTTP status/envelope is installed here.

Later application admission must validate locked customer equality, scope,
revision/path/head/sequence, order state, authority, target membership, full or
proper-subset decisions, temporal ordering and aggregate financial semantics.
The decoder deliberately does not reconstruct fake scoped Quotes to calculate
prices. Existing domain calculation and storage range validation must run before
any durable effect, including overflow/discount validation for revisions. Decoded
inputs alone cannot be persisted safely. The activation fence, maximum-history
capacity qualification, OpenAPI/client generation and full HTTP/application tests
remain separate prerequisites. No capacity trials or harness/limit changes ran.

## Local evidence

- RED: first two boundary tests failed collection because the new module did not
  exist; the failure was observed before implementation.
- GREEN: 95 focused cases covering exact/over byte bounds, cumulative chunk stop,
  UTF-8 splits, depth/escape handling, duplicate decoded keys, hostile number
  lexemes, text/IDs/times/counts, all line kinds, 1,000/1,001 edges, closed nested
  fields and decision-action restrictions.
- Initial Ruff check reported formatting/import/regex-style issues; corrected,
  then touched-source/test Ruff check and format passed. Strict mypy passed for
  the new source module.
- Runtime reused Python 3.13 and dependencies from an existing workspace venv;
  no frozen install or new-environment reproducibility claim.
- Final complete quote suite: **572 passed, 188 skipped, one existing Starlette
  deprecation warning**, 28.04 s. All skips are unavailable PostgreSQL evidence
  (including real concurrency/restore/TRUNCATE); none is claimed as a pass.
- Repository/revision-string and OpenAPI tests: **25 passed**. Final touched
  Ruff check/format, strict mypy, four-document Prettier and diff whitespace pass.
- Independent reviewer reran all final 95 focused tests and 210 additional
  bounded adversarial probes successfully and inspected the complete semantic/
  documentation delta. No substantive blocker found.
- App registration, nine router files and committed OpenAPI were compared
  byte-for-byte to the base: all 11 files unchanged. Generated API contracts are
  deliberately untouched because no route is registered.
- PostgreSQL/native/hosted/physical gates are not inferred. The full aggregate
  runtime verifier was intentionally not invoked for this finite pure boundary;
  no browser, deployment, maximum-history or CPU capacity trial ran.

## Reconciliation with merged read and catalog prerequisites

The normal merge joins the original published PR48 head
`2f74f075d28d403621b0a87c720c785eae8f3a46` and actual main47
`51c351864cec4dbf444e5f99d3c441239a4b2665` (tree
`a9bb574604373788f604209feabcfd5541033804`) in that parent order.
PR46 read contracts and PR47 catalog compatibility are now merged; the earlier
records describe their original development checkpoints, not current unmerged
status. The coordinator verified PR46 postmerge acceptance; PR47 postmerge and
this new combined PR48 candidate require their own exact-source acceptance.
The user's sequential integration approval does not authorize quote activation.

Only changelog and execution-state content conflicted; both additions were kept.
The checklist merged additively. Every production, test and generated-contract
blob from either parent is preserved exactly. In particular, the unchanged
request decoder now coexists with the read projections and explicit three-grant
current catalog. Existing Owner19 does not acquire quote grants automatically.
The incoming OpenAPI change remains exactly the catalog's two maxItems bounds;
no quote route is registered and no new request DTO is exposed through OpenAPI.

Original PR48 hosted qualification remains source-bound history: CI38805030185
passed 27 controls, Python direct/aggregate each 3,425 passed with 23 explicit
skips, and native browser groups passed direct80/aggregate80/sync20/cutover9/
clock5/expiry10/kernel14 without retries. Runtime38805030145, Security38805030133
and DCO38805030212 passed; QEMU38805030186 failed NON-QUALIFYING with original
cause unproven. These results do not qualify this newly combined tree.

Fresh combined local verification uses the existing separately frozen
all-workspace Python 3.13.5 environment from the catalog reconciliation, verified
against this tree's unchanged lockfile. Local frontend tools use Node24.19.0,
not the pinned hosted Node22.16.0. No fresh installation is claimed for this
worktree. No local PostgreSQL/native-browser/full aggregate or maximum-history
capacity qualification is attempted; the existing 16 MiB serializer specimen
is deliberately excluded from the bounded test selection. No production logic
change or new test behavior is introduced, so this merge uses deterministic
source-union proof and existing regressions rather than an artificial RED test.

Fresh local combined results:

- Bounded quote/identity/CLI/repository/CI selection: **1,366 passed, eight
  skipped, 456 deselected**, one existing Starlette warning (159.94 s). Three
  skips require real PostgreSQL; five require the hosted scanner. The explicit
  16 MiB serializer specimen and other deselected cases are not passes.
- Complete frontend core: **912 passed**; API-client core: **one passed**, with
  no failures/skips. Web/API/offline types, ESLint and full Prettier pass.
- Full Ruff check/format: **277 files**; mypy: **113 source files**. Repository
  validation and generated OpenAPI/TypeScript checks pass. Production PWA builds
  with its existing large-chunk warning; no limits are altered.
- Independent review confirmed the exact parent source union and no production
  blocker. Focused request/read/catalog tests passed **224**, with **65 explicit
  PostgreSQL skips**, plus contract checks and focused Ruff.
- Exact source union verifies **684** non-reconciliation-document paths: 666
  shared, 16 incoming main47 and two original request files. Only four additive
  reconciliation documents differ beyond those parent blobs. The prior state
  statuses are retained as historical checkpoints, with current gates here and
  in the new reconciliation block.

Local proofs do not replace fresh combined-tree hosted or postmerge evidence.
The coordinator owns publication using connector-managed account metadata;
the separate local merge has truthful Codex <codex@openai.com> provenance and DCO.
No author/committer override is supplied to the connector. Publication preserves
the exact reviewed tree, ordered parents and message; its commit SHA may differ.
