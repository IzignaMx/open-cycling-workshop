# Customer capture field limits: bounded integrity design and plan

## Admission and observed defect

This is an active V0.1 customer-integrity correction under FR-CUS-001 / R01-T030,
not FR-CUS-002 search or completion of R02-T001. Master Loop priority favors
preventing invalid retained/synchronized data over new feature breadth.
Baseline: accepted main `4b3b886c0f9c91b3732595b44db926b6fcf6bbf9`, tree
`6a1e9d2a1a3f9c28b7c42a4f1c109652645f6954`, equivalent local `c6e9432`.

The coordinator reproduced the existing builder and real controller accepting
name201/email321/phone65, returning saved with journal delta1. The domain also
accepted lengths beyond the REST raw limits and database String capacities.
A second case, `İ` repeated158 plus `@x.co`, has raw length163 but lowercases to
321 code points. Raw request validation alone therefore misses this expansion.
These are supplied local RED observations, not new hosted or PostgreSQL proof.

## Invariants and scope

- Enforce customer display name200, email320 and phone64 code points after each
  layer's existing normalization. Keep existing raw REST validation as well.
- No normalization change and no truncation. JavaScript UTF-16 code units are not
  the shared length metric; Unicode expansion and supplementary characters need
  explicit boundary cases. Do not introduce a new email/telephone policy.
- Reject before local customer/journal side effects. Keep the user's full draft
  available for correction and use a closed validation error without echoing PII.
- Backend domain create/update must reject invalid normalized values. REST create
  maps these validation failures to422; sync returns its existing conflict result
  without entity/change effects. A valid peer in the batch must still succeed.
- Preserve existing mutation identity, scope, uncertain-outcome handling and
  idempotency. Do not rewrite, truncate or delete already retained invalid work.
- No new authority, storage, migration, search, credential, infrastructure or
  M2 lifecycle implementation. A database String declaration is not a portable
  application validation guarantee, particularly under SQLite.

## Bounded implementation and verification plan

1. Retain failing local builder/controller and backend domain/REST/sync cases.
   Cover exact limit, limit+1, normalization expansion, supplementary code points,
   unchanged valid normalization and correction of the preserved draft.
2. Add minimal post-normalization checks in existing customer paths. Verify the
   failure occurs before local writes and before backend entity/change effects.
3. Prove structured REST422, sync conflict and successful valid batch peer using
   real application boundaries with existing test fixtures. Do not label SQLite
   or simulated browser results native PostgreSQL/browser qualification.
4. Run targeted tests, repository contracts, static checks and coordinator's
   combined suite; independently review the exact candidate. Record actual counts
   only when those results exist. Stop before publication or hosted execution.

## Local candidate checkpoint

Implementation is complete and independently reviewed with no remaining blockers.
Retained RED evidence includes8 backend failures and9 frontend failures before the
correction. Four independent mutation controls detect missing caps/UTF-16 counting.

- Full local Python:5391 passed,671 environment skips,12 warnings,373.53s, exit0
  (`artifacts/customer-field-lengths/full-python.log`). Skips are not PostgreSQL
  or native qualification. This run preceded only the final documentation stamp.
- Final full frontend:1246 passed. Backend focused70 and frontend focused24 passed.
- Repository contracts:175 passed before the stamp; the same repository suite is
  rerun after this documentation update, with its distinct retained log.
- Build/types/lint/format passed. Existing Vite bundle warning above500KB remains.
- Three new native PWA cases were authored;13 cases in their file were collected,
  but none executed locally because Docker/psql are unavailable. Hosted evidence
  remains pending; collection is not browser acceptance.
- Scope18 files; none matches M2 workflow trigger paths. No publication, seventh
  M2 run or new runtime authority is granted by these local results.

Logs are retained coordinator artifacts, not tracked/public repository files.
Hosted acceptance of the baseline below does not qualify changed source. Physical T1–T8/R01-T035, capacity, broader OFF-007,
SPENT40927223929, UNKNOWN41011497919 and Pages remain unchanged.

## Historical accepted baseline, not candidate evidence

[Fresh-main CI41757541938](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41757541938)
passed27/27 on the exact baseline above: Python5987 +58 exact skips,
frontend1237/API1, browser126 direct-log/126 aggregate, small repeats20/9/5/10
and kernel14 retry0. Runtime41757542023, security41757541909 and micro41757541906
were independently accepted. Large browser archives were not downloaded or
byte/trace/screenshot reviewed. No M2 workflow ran on that main push.

Retained coordinator archive receipt:
`artifacts/m2-hosted/pr85-postmerge/final/review.json`, SHA256
`04aad320c1fc887fd6436fd518c40952c378a8dcaf93ac6d12087af2bb79283d`.
This path is not a tracked or public repository file. The separately authorized
sixth M2 attempt belongs to PR85's historical evidence and is not a seventh run
or customer-fix qualification. Production machine authority remains absent.
