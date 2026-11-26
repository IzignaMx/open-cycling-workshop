# Stable conflicts for REST entity creation · 2026-11-26

## Scope and requirements

Baseline: main `618c445f0bbd51942ae8bd6293f25788c2ce936e` (merged PR123).
The [previous checkpoint](2026-11-26-source-completion-login-document.md#pr123-candidate-acceptance-and-merge-receipt--2026-11-26)
records the accepted test-only login correction and separate pending postmerge CI.
This increment addresses a reproducible REST creation error-classification defect
in the existing customer, bicycle and service-order workflows. It is bounded
V0.1 integrity work, not new release scope or completion of these business domains.

Relevant requirements are [Phase 1](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md)
FR-CUS-001 (customer creation), FR-BIK-001 (bicycle creation), FR-SVC-001 (order
creation), SEC-002 (least privilege), NFR-007 (criticality-based coverage) and
NFR-014 (versioned documentation), plus AC-008 (documented API errors, idempotency
and versioning). [Engineering §40](../05-engineering/open-cycling-workshop-platform-phase-5-repository-engineering-architecture-v0.1.md#40-error-taxonomy)
distinguishes stable public domain-conflict codes from database/infrastructure
failures. No accepted ADR, schema, permission or offline/sync policy changes.

## Reproduced problem and correction

An authorized customer POST with a supplied unused ID returns HTTP201. A second
POST with that ID reaches the existing global primary-key constraint and returns
HTTP503 `database_command_failed`, although the ID is already allocated. The
same existing-ID condition must be classified consistently at all three REST
create boundaries, with a stable HTTP409 domain-conflict response. It must not
pretend to be a temporary database outage or a successful idempotent replay.

The public error codes are:

| REST create              | HTTP409 code        |
| ------------------------ | ------------------- |
| `/api/v1/customers`      | `customer_conflict` |
| `/api/v1/bicycles`       | `bicycle_conflict`  |
| `/api/v1/service-orders` | `order_conflict`    |

The correction targets only the existing entity-ID conflict. The shared insert
boundary uses PostgreSQL/SQLite `ON CONFLICT (id) DO NOTHING RETURNING id` to
separate a successful insert from an already allocated ID. The implementation is
[`db/insert_conflict.py`](../../services/platform/src/cycling_workshop/db/insert_conflict.py),
called only by the three repositories' new REST `try_add` path. Existing `add`
methods remain intact. The database remains
the authority under competing requests; there is no read-then-insert existence
race, broad `IntegrityError` conversion or change to the actual primary key.
Other constraint/database failures must retain their real error classification.

Current authorization, organization/location admission and referenced-entity
checks occur before the insert attempt. A conflicting request must leave the
original row, change feed, outbox and receipt state intact. It returns no existing
entity fields or tenant/location information. The three REST routes retain their
existing successful-create transaction and feed behavior. Sync repository writes,
operation-ID idempotency and mutation receipts remain unchanged. A repeated REST
create is a conflict, including when the submitted content is identical; no
idempotency contract or retry policy is introduced.

## Verification and evidence boundary

The focused customer SQLite suite first produced **four expected failures**
(HTTP409 expected, HTTP503 observed) and seven passing controls, then passed
**11/11** after the correction. A later actual non-ID unique-index control
(test-only SQLite email index) also retained HTTP503 without mutation; the final
focused customer suite passed **12/12**. It includes a coherent authenticated foreign tenant,
other-location collisions, identical and changed content reuse, no-store responses,
unchanged domain/feed/outbox/receipt snapshots, authorization-first behavior and
later integrity/operational failures. Those injected storage-failure controls
verify classification/rollback, not native PostgreSQL concurrency.

The bicycle suite first observed **four expected failures / one passing control**,
then its final focused selection passed **7/7**. The service-order suite first
observed **six expected failures / two passing controls**, then passed **12/12**
including final no-store and fixture-cleanup controls. Their broader existing
suites also passed **82** bicycle and **94** service-order cases; those groups
overlap the final focused and combined selections below.

The dedicated PostgreSQL suite first produced **seven expected failures** and
three passing controls against the baseline. It then passed **10/10** cases in
**2.32 seconds**, with no skips. Six cases cover same-organization and
cross-organization collisions across all three entity types. A genuinely
concurrent cross-organization customer-ID collision observes the database
unique-key wait and yields one HTTP201 plus one HTTP409. Three actual outbox
primary-key violations retain HTTP503 and roll back the entire create. The
concurrent native proof is specifically for customer creation; the bicycle and
service-order native collisions are sequential scope controls. The dedicated
test PostgreSQL container was removed and its absence confirmed; the safe receipt
is `artifacts/workshop-create-conflict-20261126/postgres-local-receipt.json`.
That receipt's bicycle-router hash predates a final response-description wording
alignment only. The collision implementation is unchanged; final OpenAPI checks
below cover the description alignment rather than relabeling the earlier hash.

The OpenAPI guard first failed for the missing HTTP409 declarations, then all
**three OpenAPI tests** passed. Full strict mypy passed **127 source files**;
Ruff lint and formatting passed **363 files** at the checked source. Regenerated
OpenAPI changes only the three HTTP409 response descriptions; the generated
TypeScript client is byte-identical, and both generation checks passed. Final
source review found no blocking findings across the three routes.

The broader customer/bicycle/service-order/sync/inventory/contracts/repository
selection passed **1,763 tests**, with **79 environment skips** and one existing
Starlette warning (88.93 seconds). Its skips include the ten new PostgreSQL
cases; the separate native run above supplies that scoped evidence. Other skipped
integration cases are not qualified by this selection. It was collected before
the twelfth customer control, whose passing result is recorded separately.

The final focused and repository selection passed **261 tests**: 12 customer,
seven bicycle, 12 service-order, three OpenAPI and 227 repository tests, with one
existing Starlette warning. Full Ruff lint/format, strict mypy, the repository
verifier and diff checks passed. The real local HTTP smoke passed synthetic
health/readiness/login/push/pull; API-client core **1/1** and its typecheck passed.
These invocation groups overlap and must not be added as unique cases. Exact
successor hosted CI remains pending; no broad frontend/browser or production
release acceptance is inferred from this server-only correction.

## Remaining product and operations gates

V0.1 remains **partial**. The [inventory audit](2026-11-25-project-inventory-audit.md)
retains every FR-INV-001–012 capability gap and the tested inventory boundaries.
No real workshop data, physical inventory count, installed target, recovery volume
or deployed runtime is changed here. Physical T1–T8/R01-T035, G1–G6, installation
restore, quote capacity/activation and operational deployment remain separate.
The original browser/CDP internal cause remains unproven; this REST correction
neither resolves nor reclassifies that historical evidence.

## PR124 initial hosted evidence and Security blocker · 2026-11-26

Published candidate `9921b54073b1d756c6462e63dd7505348fed08b2`, based on
`618c445f0bbd51942ae8bd6293f25788c2ce936e`, was tested as synthetic merge
`5a232e5c` with tree `5aa2e88ae0e2853beeef9023b6f3700744883a62`.
[CI45811741910](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45811741910)
passed all jobs/steps: **6,813 Python passes / 58 intentional skips**, **1,805
frontend passes**, **1 API-client pass**, **146 direct and 146 aggregate browser
passes** without reported flakes/retries, and separate zero-retry groups
**20 / 9 / 5 / 10**. CI, DCO, Local runtime, public preview and microfixture
concluded successfully. These source-bound results do not qualify a later
scanner-policy/documentation successor automatically.

Independent inspection of Python artifact `15114159444`, SHA-256
`099f02dd7717e16d4dfc97ff44a74a621406fac21ac7a6b2ec8c111a50a7f53c`,
verified all ten new PostgreSQL cases' setup/call/teardown phases. The receipt
records PostgreSQL **18.4**, psycopg **3.3.4** and cleanup evidence. This separately
establishes the collision/concurrency/rollback cases authored for this change;
it does not replace physical or installation qualification.

[Security45811741828](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45811741828)
**failed** at Gitleaks. Safe metadata artifact `15112443031` records two historical
findings for the same public execution-state test-count value, once in the source
commit and once in the synthetic merge. The field is the OpenAPI guard's public
RED/GREEN count at line 29 of that candidate's YAML. Its nonsecret provenance was
checked; these findings are not two credentials. The original failed workflow
and its metadata remain preserved, without rerun or retrospective success.

The bounded correction extends the existing reviewed false-positive policy only
for that exact public value and exact execution-state path under the existing
rule. It retains default rules, full-history scanning and directory-based
policy canaries, including negative controls for changed values, other paths and
synthetic secret-shaped canaries. No scanner is disabled and no broad path/rule exclusion is introduced.
The pinned Gitleaks **8.30.1** canary first failed on the reviewed public count
before the exception, then all **24/24 canary cases** passed. Negative controls
retain detection for a changed value, another path and another default rule on
the same path. The policy structure guard likewise failed before the fifth exact
exception was added, then passed. The executable release checksum was verified.

A local precommit history scan using the corrected working-tree policy reported
**zero findings**, **588 scanned / 596 reachable commits** and **28,747,574 bytes**
at existing HEAD `9921b540`. This is not a scan of a future corrected commit or a
later hosted Security success. The native policy suite then passed **15/15 tests** in **75.09 seconds**, with
zero skips, covering all four mutation classes across the five exact exceptions.
Independent source review found no blocking findings. The selected CI-verifier,
CI-contract and repository compatibility tests passed **440/440** in **7.82 seconds**,
with touched Ruff checks passing. REUSE **3.3** passed
licensing/copyright checks for **1,150/1,150 files**. The locked Python audit using
pip-audit **2.9.0** reported no known vulnerabilities across **41 active packages**,
with two platform-marker exclusions. Local Trivy was not run and remains a
separate hosted check. These results do not broaden the false-positive exception
or establish a general absence of security issues.

The final exact commit scan and the successor's required hosted Security result
remain pending at this authored checkpoint. PR124 is not fully qualified or ready to merge until that
required hosted result is observed. Product code, authorization, sync and deployment
are unchanged by the scanner-policy correction.

## Corrected PR124 acceptance and merge · 2026-11-26

Corrected candidate `9e8c718c51047ea792975a09ace1fb8ba6c2b7a9` was accepted and
[PR124](https://github.com/IzignaMx/open-cycling-workshop/pull/124) merged as
`382fa000ebd1b72fac3a1dfc6ea60ac0df712021`; candidate and main share tree
`5533ec24c223973761f8c9629e8efd102b5fc952`.
[CI45865062069](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45865062069)
reports **6,813 Python passes / 58 intentional skips**, **1,805 frontend passes**,
**1 API-client pass**, **146 direct and 146 aggregate browser passes** without
reported flakes/retries, and zero-retry groups **20 / 9 / 5 / 10**.
All six candidate workflows concluded successfully, including the corrected
Security run; its safe evidence artifact `15140655994` was verified. The earlier
Security45811741828 failure remains a failed historical attempt, not a rerun or
retrospective pass.

Independent review of the corrected full-Python artifact `15141365529`, SHA-256
`32faaa13a1c06990cdbb05d12e83f2a8594c5174fe22481326b2828642098571`,
bound it to the exact candidate tree and verified every setup/call/teardown phase
of the ten new PostgreSQL tests plus cleanup absence. Browser counts above are
reviewed-log evidence only; no independent browser-archive review is inferred.
This receipt supersedes earlier candidate-hosted/Security-pending statements
only for the accepted corrected candidate.

Fresh merged-main repository checks passed **227 tests**. The separate
[main CI45888038861](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45888038861)
is pending at this receipt; its outcome is not inherited from candidate CI.
The REST behavior is integrated, while physical, actual stock, recovery,
release and deployment gates remain open.
