# Customer command admissibility: bounded integrity design and plan

## Admission and baseline

FR-CUS-001 / R01-T030 admits this active V0.1 integrity correction. It is not
FR-CUS-002 search, R02-T001 completion or a bypass of V0.1 physical gates.
PR86 fixed post-normalization lengths; this increment addresses new commands
that otherwise queue values the server rejects or silently coerces.

Accepted baseline main `23def8f45bc02e16b9f7f0b3263ed34f97a2da02`, tree
`409a61aa3a33e4f4c3ad19a03cd572c64c052599`, equivalent local `d7d3d8d`.
[Fresh-main CI41780887753](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41780887753)
passed 27/27: Python: 6,004 passes + 58 exact skips; frontend: 1,246; API: 1;
browser: 129 direct-log and 129 aggregate. Small repeats: 20/9/5/10; kernel: 14;
zero retries. The three customer-length
PWA cases passed in the direct log. Runtime 41780887756, security 41780887709 and
micro 41780887820 were accepted. No M2 workflow ran on that main push.
Large browser archives were not downloaded or byte/trace/screenshot reviewed.

Retained coordinator archive receipt:
`artifacts/customer-field-lengths/pr86-postmerge/final/review.json`, SHA256
`b32b210d3ab0c28895b1d9f11b79cc7f290e40c9a9cc0fe6c88bf5501ee5636c`.
This is not a tracked or public repository file. These counts do not qualify the
new candidate, and the prior length record remains its historical source snapshot.

## Validator inventory and bounded decisions

The source inventory covers `apps/web/src/features/customers/local-customer.ts`,
`CustomerQuickCreate.tsx`, runtime capture outcomes and repositories, plus
`services/platform/src/cycling_workshop/customers/domain.py`, customer REST schemas
and sync schemas/service. Existing normalization stays unchanged in each layer.

- **Name:** JavaScript trim/whitespace collapse differs from Python whitespace
  splitting. U+0085 and U+001C–U+001F can survive frontend preparation but become
  a blank server name; U+FEFF behaves differently in the other direction. Validate
  admissibility of the backend projection without replacing existing prepared values.
- **Email:** the builder lacked the existing domain grammar
  `[^@\s]+@[^@\s]+\.[^@\s]+`. Single-label `a@b`, embedded whitespace and missing
  components require closed local rejection before journaling. Project Python
  edge whitespace for validation only; preserve the prepared journal/optimistic
  string and existing lowercasing. Do not invent a stricter email standard.
- **Native form:** `type=email` is a separate browser acceptance boundary. Native
  grammar, Unicode and form-submission behavior need actual native browser proof;
  source inspection or simulated controller tests are not that proof. Do not add
  noValidate or redesign the form's policy as a side effect.
- **Phone and lengths:** frontend trims ends; backend removes whitespace. Keep
  both policies and PR86 code-point caps of 200/320/64. The local cap can be stricter
  than the server projection; this is not a promise of identical acceptance sets.
  No truncation, relaxed cap or normalization unification is admitted.
- **Types:** generic sync payloads admit non-string values. New domain commands
  must require a string name and string-or-null contacts, not stringify names or
  silently turn malformed contacts into null. REST's typed boundary remains.
- **Null and omission:** optional create contacts remain allowed; explicit null
  clears update contacts, omission preserves them, and normalized blanks remain
  null. A null display name is invalid. Preserve the existing update sentinel.
- **Unknown fields:** create unknown keys compatibility is unchanged. Existing
  update unknown-key rejection is retained; no general schema redesign.
- **Replay and isolation:** receipt-first handling remains before new validation.
  Do not rewrite/delete retained work or invalidate an already acknowledged
  historical receipt. New invalid sync items conflict individually without
  entity/version/change effects, while a valid batch peer still succeeds.
- **Identity and scope:** no changes to capabilities, mutation identity, uncertainty,
  storage, migrations, credentials or production machine authority.

## Implementation and verification plan

1. Retain real builder/controller RED for malformed emails and backend-blank names,
   with journal/entity delta zero, closed errors and a recoverable editable draft.
2. Reproduce strict-type failures through domain and sync boundaries with correct
   fixtures; preserve null/omission, normalization and historical replay cases.
3. Implement only the existing-domain projection and strict new-command checks.
   Test valid peers and absence of row/version/change effects on rejection.
4. Run focused tests, full local suites, repository contracts and static checks;
   independently review the exact source. Collect meaningful PWA cases separately.
   Simulated/SQLite outcomes are not PostgreSQL or native browser qualification.
5. Stop after the locally reviewed candidate. Publication and hosted execution
   need separate approval; no seventh M2 permit is granted.

## Current local evidence

Implementation and local validation are complete; independent review accepted the
production changes and tests. Frontend behavioral RED is retained
under `artifacts/customer-admissibility/`. The initial backend artifact encountered
`NoReferencedTableError` during fixture setup: it is not valid behavioral RED.
The earlier 12-failure artifact remains invalid evidence of behavior. With repaired
fixtures, `artifacts/customer-email-parity/backend-tracked-red.log` records 27 valid
behavioral failures and 68 passes: 26 domain type cases plus the real API batch
accepting a malformed item instead of conflicting. These are distinct from the
invalid fixture run, not an aggregate failure count.

- Full local Python: 5,432 passed, 671 environment skips, 12 warnings, 384.99 s,
  exit 0 (`artifacts/customer-admissibility/full-python.log`). This completed
  before the final documentation-only stamp; skipped checks are not qualification.
- Final full frontend: 1,256/1,256 passed. Focused backend: 108 passed with one
  existing warning. Repository: 178 passed, rerun after this stamp in the separate
  `artifacts/customer-admissibility/docs-final-repository-green.log`.
- Static checks, types and build passed; the existing chunk-size warning remains.
- Independent review checked all 1,114,112 code points against the 29 Python
  whitespace characters and detected three injected mutations. This validates
  the projection, not identical frontend/server/native acceptance sets.
- One new native PWA case was authored; 14 cases in the file were collected,
  zero executed locally. Native browser/PostgreSQL and hosted acceptance remain
  unqualified for this candidate.
- No publication, hosted execution or seventh M2 authority follows from these
  local results. Stop at the reviewed local package pending separate approval.

Logs are retained coordinator artifacts, not tracked/public repository files. Prior PR86
counts do not transfer to changed source. Physical T1–T8/R01-T035, capacity,
SPENT40927223929, UNKNOWN41011497919, broader OFF-007 and Pages remain unchanged.
