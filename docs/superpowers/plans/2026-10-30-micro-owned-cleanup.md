# Microfixture owned cleanup after incomplete creation

Status: bounded corrective design independently accepted for mock-first implementation. Baseline main
`7c69071ab322d8a0cdcc80bf15633feac39aa593`, tree
`eb7e7d01c31d617dc32efbc58ec3ff4a2b2ec971`.

## Evidence and invariant

Postmerge run41011497919 failed with command_timeout during canary_containment
(elapsed5.238 seconds), empty completed identities, cleanup failed and independent
finalizer unverified. Neither exact command nor historical CID/owner files were
retained. Empty identities and generic runner orphan-process cleanup do not prove
container absence. Historical cause and owned-resource outcome remain unknown.

A separate mock-only reproduction proves a code defect: primary cleanup and the
workflow finalizer parse every CID hint as a complete ID before reconciling strict
ownership. An empty/partial hex hint therefore prevents removal of an otherwise
exact manifest-owned container. This is not proof of the historical cause.

## Selected correction

Reuse the existing strict full_reconcile algorithm in both micro cleanup paths,
not a second owner matcher. Empty/partial hex is an incomplete hint, never an ID
passed to Docker. Require the existing exact manifest, random token, role name
and image. Reject malformed hints, missing required manifests, identity mismatch,
foreign complete IDs and failed listing/removal. Preserve creation uncertainty
as a failed workload even if owned resources are independently removed.

Reuse diagnosed_full_reconcile for fixed-code observations. Preserve its existing
full-Python default and behavior; any added diagnostic kind is a closed allowlist.
Micro diagnostics contain only stage, fixed failure code and CID completeness
states, not raw IDs, manifest, commands, exception text or credentials. Diagnostic
sink failure cannot prevent removal or change the authoritative failure. Retain
primary and finalizer diagnostics as separate files, explicitly not workload
qualification. Add a fixed operation label to the existing micro stage so future
create/inspect/start/resource/privilege boundaries can be distinguished without
raw command output.

No timeout/resource increase, dependency, permission or workload change. Existing
ordinary automatic CI validates the new source; do not rerun failed historical
runs. Ownership measurement40927223929 is permanently spent and unrelated: never
replay it, rotate its identity or activate it. Pages remains unchanged.

## Rejected alternatives

- Ignore invalid CID files or remove by a name/prefix alone: unsafe ownership.
- Raise create timeout or retry the old head: neither diagnoses nor fixes cleanup.
- Upload raw ownership files/command output: unnecessary disclosure and no proof
  that the old run had any particular contents.
- Duplicate reconciliation: existing full-route behavior already has strict tests.

## TDD and acceptance

1. RED actual supervisor and extracted workflow-finalizer paths with empty/partial
   hints plus an exact mock-owned object. No Docker/process/database execution.
2. GREEN through existing reconciliation; complete-ID case retained. Workload
   remains failed after uncertain creation even if cleanup removes the object.
3. Negative exact-ownership matrix: malformed CID, missing/malformed manifest,
   wrong image/token/name, foreign full ID, list/inspect/remove failures and a
   still-present object. No broad deletion or false absence.
4. Diagnostic privacy/size/sink-failure and default full-route compatibility.
   Verify fixed operation labels and unchanged budgets/workflow permissions.
5. Full retained Python tests in hosted fixed limits; locally run available
   stdlib-only tests; an existing recovered Python3.13 environment supports the
   full local suite but cannot replace missing PostgreSQL/browser runtime proof.
   Require every named terminal exit receipt before combined local pass claims.
6. Independent exact-patch review, normal PR qualification, then fresh postmerge
   source/artifact checks. New success cannot repair the unknown old cleanup.

PR75 transition behavior has independent candidate101/101 direct+aggregate proof;
its fresh main qualification remains partial while this companion failure is
unresolved. Other postmerge checks continue independently, without duplicate runs.

## Local corrective evidence

19 new stdlib mock cases passed; focused retained operations suite304 tests plus15
subtests passed. Full standard local pytest in an existing Python3.13.5 environment
collected5,576:4,905 passed,671 environment skips,12 dependency/deprecation warnings
in513.44 seconds. No database/runtime activation variables, installation or
measurement were used. Original behavioral RED and initial Ruff SIM117 failure
remain recorded; the corrected focused source passes Ruff and formatting.
Independent exact four-file implementation/test/workflow review accepted ownership,
privacy, unchanged limits and both-finalizer-stem behavior. Fresh hosted proof is
still required; no local or later proof repairs the historical unknown outcome.

## First hosted invocation failure and bounded correction

PR76 head eb2baffb, micro run41018864858, failed while importing the diagnostic
writer: the workflow invoked the file directly, so Python did not expose the
repository root as the scripts package. The import preceded primary cleanup.
The independent inline finalizer completed strict ownership reconciliation; its
observations remain explicitly not workload receipts. No primary workload receipt
exists and the second record specimen was skipped. Do not infer workload success
or historical41011497919 cleanup from that finalizer.

Use the module entrypoint from the repository root for both existing workflow
commands, without changing arguments or timeouts. Import the diagnostic writer
only inside its best-effort finalization scope: unavailable diagnostic imports
must neither prevent reconciliation nor replace an original cleanup exception.
Add mock import-failure regressions for both cleanup success and failure, plus
exact workflow/module invocation parity verification without a container trial.
Package-import tests alone did not exercise the deployed entrypoint; preserve
this lesson and require the actual invocation shape in future proof. Fresh hosted
qualification follows a reviewed source correction, never an identical-head rerun.

## First hosted reporting incompatibility

The same candidate Python shard A stopped with duplicate_phase while new unittest
subTest matrices emitted multiple call reports for one collected node. Its result
is incomplete, not a full pass; the retained diagnostic does not expose the first
underlying assertion, so do not invent that attribution. Both shards' primary and
independent owned cleanup was verified absent; the failed sealing step is not a
failed container-removal claim. Shard B passed2,153/47 expected skips.

Expand all15 scenarios in the three matrices into distinct collected test methods,
preserving every assertion and the strict verifier. Exercise actual pytest report
invocation on the mock-only file and verify unique setup/call/teardown phases and
complete collection; retain negative duplicate-report rejection. Local pytest
without the production reporting contract did not establish hosted compatibility.
Consolidate this test-only correction with the invocation fix and require fresh
whole-suite receipts before any combined local pass claim.

## Consolidated corrective local checkpoint

The corrected source passes323 focused tests with no subtests and the full local
standard pytest suite:5,595 collected,4,924 passed,671 environment skips,12
deprecation warnings, exit0 in681.61 seconds. The earlier import-only and
pre-environment-isolation full runs remain historical, not proof for this tree.
Actual pytest observation confirms34 independent mock nodes/102 unique phase
reports; a deliberate duplicate-subtest fixture remains rejected. Four nested
pytest integration cases cover clean/hostile parent environments and positive/
negative report shapes. Strip inherited proof/database/plugin/addopts activation
and explicitly disable autoload in that mock-only child; no production verifier
or resource limit changes. Fresh hosted qualification is still required.
