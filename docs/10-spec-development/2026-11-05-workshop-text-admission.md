# Autonomous tests: persistable workshop text

## Accepted baseline and bounded selection

[PR93](https://github.com/IzignaMx/open-cycling-workshop/pull/93) is accepted at
main `7e768ee37cb5954dbcd875a138c9dcc6464645b1`, tree
`e5ba83b6e64772714a95223527ac4bd091ea35ae`.
[Fresh-main CI 42071971585](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42071971585)
passed Python 6,512 plus 58 exact skips, including all 85 parser regressions;
frontend 1,299, API one, aggregate 27/27, browser 133 direct/133 aggregate,
repetitions 20/9/5/10, expiry ten and kernel 14. All ten checks and four ordinary
workflows succeeded on attempt one. Independent small-artifact digests, source,
cleanup and bounded receipts were verified; large browser archives were not
inspected. The PR receipt supersedes its historical pending source snapshot only
for that accepted source, not this new change.

This pass follows the request to continue useful autonomous tests while physical
T1–T8 remain deferred, not accepted. Master Loop prioritizes data integrity and
sync correctness. OFF-005/OFF-008 and canonical R01-T018 remain partial: invalid
items must be permanent conflicts without aborting independent valid items.
The earlier [create-location validation evidence](2026-11-05-location-create-validation.md)
remains part of that same requirement/task chain; the unique traceability pair
now points here without discarding the earlier source-bound receipt.
This is a technical PostgreSQL/UTF-8 admission boundary, not a new domain model,
normalization policy or architecture decision. No ADR or migration is introduced.

## New observations and evidence limits

- 29 new branding/blob probes passed: malformed replacement requests preserve
  profiles, audit content and files; exact tenant namespaces, unsafe-file refusal,
  bounded reads, noncanonical Base64 and positive Unicode/PNG compatibility hold.
- 16 new session controls passed: current revocation/scope/grants remain enforced;
  rejected logout leaves registered tables unchanged. Eight proposed duplicate
  Authorization refusal assertions were RED, but they are **not confirmed defects**.
  The framework selects the first credential and no repository contract requires
  duplicate refusal. No bypass or proxy behavior was demonstrated. That policy
  is not changed by this correction.
- Twelve workshop create fields and transition notes admitted NUL at domain
  level; customer REST/SQLite returned 201. Installed psycopg `StrDumper` and
  literal adaptation reject NUL without a connection. This is actual driver
  evidence, not a PostgreSQL server run.
- A pre-execute driver-hook simulation aborts before the valid following sync
  item, with no persisted customer/change/receipt. Its HTTP 500 is outside normal
  DBAPI-to-SQLAlchemy wrapping and must not be described as the real PostgreSQL
  status. The existing wrapped database-error handler returns sanitized 503.
- Legacy sync actually admits escaped lone-surrogate payload text, then SQLite
  encoding fails with 500 before the following valid item. Typed REST already
  rejects that surrogate with safe 422; the earlier REST-500 hypothesis is false.
  Strict protocol one already refuses it with 422/invalid_canonical_command.

Original observations are retained separately from intended refusal tests: nine
observation cases passed and four prospective admission assertions were RED.
This proves malformed text escapes permanent item validation; it does not prove
an exploit, generalized outage, data loss or PostgreSQL concurrency behavior.

## Correction contract

Reject NUL and lone UTF-16 surrogates without deleting, replacing or normalizing
them. Preserve all other Unicode scalar values, composed/decomposed forms,
supplementary characters, allowed whitespace/control behavior, nulls and existing
length/normalization semantics. Apply only to known persisted text and known
identifiers before their database lookups, across the three existing workshop
entities. Validate transition action before it can enter a reflected diagnostic.

Preserve current authorization and writer admission, existing receipt replay
before payload validation, strict canonical proof and its whole-request surrogate
refusal, ordinary unknown-action semantics and ignored extra payload metadata.
NUL remains representable in canonical JSON; it is refused only where the text
must be persisted or bound as an identifier. Do not reclassify unexpected database
errors or add a generic recursive payload scanner. No schema, dependency,
workflow, skip-ledger or protocol change.

The intended result is safe REST rejection before effects and legacy/strict NUL
item conflict with valid neighboring commands and replay preserved. Unrelated
read-route/path input hardening is outside this write-admission scope.

## Tests-first and independent verification

The first tracked matrix produced 122 RED failures and 24 passing controls;
three additional transition-action cases were separately observed RED before
that guard. Final retained regression file: 169 passed, no skips. Later added
coverage is not described as individually observed RED. One initial test count
omitted the valid command's outbox event; it was corrected to require that event,
without weakening invalid-item assertions.

The nearest customer/bicycle/order/sync suites passed 997 cases with five existing
PostgreSQL environment skips. That collection preceded the final three REST note
cases, which all passed in the final 169. Independent review repeated the frozen
169, passed 22 additional probes and found no blocker. It reproduced the legacy
transition-action surrogate failure before confirming the repair. Exhaustive
helper probing preserves all 1,112,063 other Unicode code points and rejects
exactly NUL plus the 2,048 surrogate points.

Eight genuine PostgreSQL regressions were added under the existing guarded
administration test fixture. They are collected but locally skipped because no
PostgreSQL server/tooling or test URL is configured. They need hosted execution,
not a skip-ledger exemption. Driver-hook/SQLite results do not replace them.

Ruff/format, ESLint, TypeScript, application mypy (126 files), OpenAPI/generated
client contracts and repository verification passed. Repository 194 passed after
correcting a duplicate traceability pair; the existing unique-pair rule remains
unchanged. The first full run had 6,059 passes and that one documentary failure;
its collection preceded the last three REST note cases. The final complete run
against frozen production/tests passed 6,063 tests, with 685 environment skips,
12 existing warnings, 490.10 seconds and exit zero. The skips include all eight
new PostgreSQL cases, which remain unexecuted locally. This receipt was stamped
after the full run; repository and the 169-case regression file are rerun afterward.
No hosted acceptance is claimed for this candidate. Frontend runtime, PWA build
and native browser were not repeated for this backend-only correction.

Ignored evidence is retained under `artifacts/autonomous-boundaries-20261105/`.
The source baseline, original observation logs and proposed-policy RED assertions
remain distinct from correction regression results. Independent reviewed
production/test hashes are retained with the review receipt.

## Unchanged gates

No browser launch retry after the prior socket restriction; no real user-data
restore, non-ephemeral target, physical device, deployment or external provider.
Physical T1–T8, R01-T035, OPS-GATE-006, capacity, M2, SPENT40927223929,
UNKNOWN41011497919 and Pages remain unchanged. New publication and exact-source
hosted qualification need applicable authorization; PR93 is baseline only.
