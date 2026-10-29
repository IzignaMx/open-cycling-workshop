# S2a · Deterministic quote-service lifetime characterization

> **Current source receipt · 2026-10-29:** [PR69](https://github.com/IzignaMx/open-cycling-workshop/pull/69)
> merged `73661dbe86d54e19cad464f48e959cd001d202b7`, tree
> `2c06102f24a42d6188a4d5e92e9f36d82698dc82`. Independently accepted fresh
> [CI40842539417](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40842539417):
> 27/27 aggregate controls; 5,085 collected / 5,027 passed / 58 expected skips;
> all four S2a cases, 55 S1 cases, 14 JWT cases, eight PostgreSQL cases, six
> restores, dual cleanup and runtime/browser evidence passed. Earlier local-only,
> pending and failure statements below are historical checkpoints, not current
> publication status. The new cases remain deterministic SQLite characterization;
> cleanup-arriving cancellation precedence, hard cancellation, capacity, physical
> acceptance and activation remain unqualified. No new deployment authority.

Assistant-selected bounded design under delegated local implementation authority.
Base: `72927ca56d8337a07f5b9813902074d87523e920`. The existing quote persistence/
online command boundary and original deadline/receipt semantics remain normative.
This increment adds tests, not a cancellation executor or newly approved behavior.

## Choice and scope

Extend the existing application-service SQLite test module and reuse its database,
actors, execute, totals and command fixtures. Four exact missing branches:

1. CancelledError raised during response encoding, after effects exist but before
   commit: preserve the exact cancellation object, roll back once, invoke the
   hook-release path, never call commit, preserve original history/totals/order state.
2. Original SQLite commit returns, then a synthetic CancelledError: propagate that
   same object without returning success; fresh same-ID/proof replay must return
   the captured exact receipt with one committed effect tuple.
3. Original commit succeeds then advances the injected original clock beyond its
   deadline: no returned success, quote_request_unavailable/outcome_unknown,
   fresh same-ID exact receipt replay and no additional effects.
4. Only the hook-release method raises OSError after acknowledged commit: unavailable/unknown,
   cleanup_unverified and unusable session, no success return; fresh same-ID exact
   receipt replay. This is not the existing combined ACK-loss/hook-error case.

Characterization may pass against unchanged production. Demonstrate sensitivity
with targeted temporary mutations of relevant existing branches, observe each
selected test fail, restore exact source and rerun green. Never label that as a
new production bug or retain a mutation. Prefer this over duplicating the existing
seven-stage atomicity matrix or adding an executor/ledger. A discovered actual
behavior defect stops implementation for diagnosis/design review.

## Boundaries

No expectation for cancellation first arriving during cleanup: precedence is
unsettled and remains a separate design gate. No actual PostgreSQL/network COMMIT
loss, asynchronous signal delivery, hard termination, bounded cleanup/backend
absence, capacity, deployment, grants, routes or module SDK claim. Tests use real
SQLite fixture commits with synthetic fault/clock injection only. Existing resource
budgets and all production files remain unchanged. No remote writes authorized.

Narrow status reconciliation may record immutable accepted M0/S1 source receipts;
retain old failed runs, local unqualified evidence, canonical M0 schema/profile
and its source target. Pending receipts must not be invented.

## Evidence precision and accepted prior receipts

SQLite installs no PostgreSQL budget hook. These cases prove release-path
invocation/failure handling, not removal of an installed PostgreSQL event hook.
Replay comparisons use canonical receipt content through the existing JSON helper;
they do not assert identical whole response bytes (`delivery` changes on replay).
The committed fixture receipt is captured before commit for exact content comparison.

The coordinator independently accepted these immutable earlier receipts, now
reconciled narrowly in state/checklist. They do not qualify this new S2a package:

- [PR64](https://github.com/IzignaMx/open-cycling-workshop/pull/64): merged
  `bd2dbd6b5a89631e0f95602220cb861c9a6cccc2`, tree
  `7cd64ff4b5d42a0074d50d6b4cf94f5a9700472d`, fresh
  [CI40668763286](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40668763286):
  27/27; 4,978 collected, 4,920 passed, 58 expected skips, all 83 descriptor cases.
  M0 remains data-only with its original `ocwp-source:a960bdd` target. Historical
  failed NON-QUALIFYING QEMU40668763297 is retained, not reclassified.
- [PR68](https://github.com/IzignaMx/open-cycling-workshop/pull/68): merged
  `72927ca56d8337a07f5b9813902074d87523e920`, tree
  `2fffef9f478f714d6daea2ed77f3270f9b20bd64`, fresh
  [CI40831394467](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40831394467):
  27/27; 5,081 collected, 5,023 passed, 58 expected skips, all 55 admission cases.
  S1 remains unmounted/cooperative-only. Prior local RLIMIT_AS failures and
  unexplained whole-run JWT crash remain historical evidence, not erased.

## Local characterization evidence

Unchanged production baseline: 25 application-service tests passed, including
four new cases. Four targeted mutations each produced one expected failure:
normalize cancellation (each before/after-commit case), omit the post-commit
checkpoint, suppress classification when only the release method fails. All
production bytes were restored and verified; no production bug is claimed.
Final affected service/driver/recovery/request/admission/privacy/logging suite:
245 passed, zero skips, one existing Starlette warning. Full collection: 5,085
cases (four added). Ruff, format and generated
contract checks passed. No whole-suite rerun under the already-demonstrated broken
local address-space harness. Hosted exact-package qualification remains required.
