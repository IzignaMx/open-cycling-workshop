# M2 lifecycle and restore: bounded anti-resurrection proposal

2026-11-03. **Proposal only; no implementation or execution authorization.**
Source inspected: `b5db35bd2bbb39848ce408e86ee31f9e4c00dffc`.
This document does not authorize persistent access, credential issuance, a new
storage service, production changes, publication, another hosted run or merge.

## Recommendation

Keep the existing laboratory disposable: restart requires a fresh installation
and fresh credentials; restored databases are not admitted. The next step is a **product-policy decision: is continuity across restore
actually needed, or is explicit fresh enrollment acceptable?** No model or
implementation should precede that decision. First distinguish what the current
process-local witness protects from what it cannot protect.
A durable anti-resurrection promise cannot be built entirely from values inside
the database or backup being restored.

If continuity across restart/restore is ultimately required, select and review
an independently protected witness and its recovery owner before implementing
that promise. Until then, missing or uncertain witness state means unavailable,
never automatic re-enrollment from restored rows.

## Evidence boundary

The retained fifth laboratory receipt, run `41568644741`, reports 19 successful
checks, all 16 supervisor milestones, and a stopped API with 13 completed service
checks. Its independent cleanup receipt reports owned containers absent and root
removed. Tested merge commit `40740e51b1d24d04af49479b24d2eb0d01483d24`, tree
`106e11df74b4e656c4b6227610648b3466c3e436`; this is distinct from this document's
inspection commit. Local retained records are:

- `artifacts/m2-hosted/hosted-independent/fifth/result.json`
- `artifacts/m2-hosted/hosted-independent/fifth/cleanup.json`
- `artifacts/m2-hosted/hosted-independent/fifth/lineage.json`
- `artifacts/m2-hosted/hosted-independent/fifth/final-review.json`

These paths refer to retained local evidence archives, not files promised in the
tracked public repository. They were read here without a new remote fetch or
runtime execution. The [current acceptance reconciliation](../../10-spec-development/2026-11-03-m2-laboratory-acceptance.md) records the updated checkpoint. Their checks cover the bounded synthetic PostgreSQL 18.4,
TLS, process isolation, read/revoke ordering, timeouts and disposal experiment.
They contain **no durable restore or external witness rollback check**. API
service results remain API self-reports validated by the supervisor; independent
cleanup proves the stated absence, not cryptographic erasure. Earlier failed
attempts' causes and historical cleanup gaps are not rewritten by a later pass.
Some existing execution-state/manual-checklist sections still describe the
fourth-attempt checkpoint; this proposal does not silently reconcile them or
claim that their historical pending fields negate the fifth receipt.

## Existing source boundaries

| Boundary          | Actual source and present guarantee                                                                                                                                                                                          | Limit                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Identity          | `tests/labs/m2/authority.py`: `MachineScope`, `issue`, `_validate`; installation, organization, exact location, dataset incarnation, machine, run and generation must agree. `models.py` keeps lab metadata separate.        | A matching identifier is not proof that the database is the latest authorized state. No production installation model is introduced.                                                           |
| Process witness   | `LabAuthority.__init__`, `_Witness`, `_validate`: random `_run_id` and witness map live outside the DB, in the API process. Witness binds scope, issue/expiry times and elapsed deadline.                                    | Not durable, not independently administered, not a trusted anti-rollback service. VM/process-memory snapshot restoration is outside the guarantee.                                             |
| Lifecycle         | `_change`: rotation commits verifier/generation/audit, then installs replacement witness under the local barrier. Revoke clears verifier and sets revoked; grant reductions and disable update protected DB rows with audit. | Revoke/reduction/disable do not record an independent witness tombstone or policy revision. A hypothetical rollback of those DB fields within the same live run is not covered.                |
| Read barrier      | `_rows`: organization compatibility, installation, then machine row locks. `read` and `_change` share a local bounded barrier; `read` rechecks scope/time before completing cleanup.                                         | Locks order ordinary cooperating transactions. They do not authenticate a restored database or stop a privileged snapshot replacement. Multiple independent API authorities are not qualified. |
| Restart/bootstrap | `runtime_authority.py`: `PostgresLabAuthority._build_engine`, `_initialize`; exact manifest/version/cluster identity, reject existing DB, create fresh template0 DB, reject populated fixture schema.                        | This rejects adoption; it is not a backup restore implementation. Source tree, nonce, DB OID and cluster name are ownership checks, not durable freshness or revocation evidence.              |
| Time              | `_clock`, `_sample`, `read`: UTC plus CLOCK_BOOTTIME high-water checks; original 15-minute run ceiling, per-credential deadlines, sticky refusal on clock faults.                                                            | Elapsed deadlines are not reconstructed after restart. Clock alone cannot prove that a recently revoked credential stayed revoked after rollback.                                              |
| Disposal          | `close` distinguishes admission closed from verified cleanup; runtime authority drops only its owned DB. `m2_lab_cleanup.py` independently checks exact owned resources.                                                     | Failed cleanup remains failed. No secure erasure, persistent tombstone retention policy or historical absence inference.                                                                       |
| Connector         | `connector.py`, `runtime_client.py`: bounded current fetch, exact trusted scope, disposable projection, no automatic retry/refresh or stale-current fallback.                                                                | Catalogue pages are not one cross-page snapshot; returned bytes cannot be recalled after revocation. No durable remote scope attestation protocol.                                             |

The existing `test_restored_old_database_rows_do_not_reconstruct_external_run_witness`
in `test_authority.py` copies installation/machine rows into another authority and
expects refusal. It does not restore a complete database into the same running
process. `test_new_run_never_accepts_old_credential_and_close_is_terminal`, clock,
rotation/audit-failure and read-before-revoke tests support their narrower names.
`runtime_service.py` adds actual PostgreSQL read/revoke ordering checks. None
establish rollback resistance for a persistent witness.

**Source-derived counterexample, not executed in this design task:** preserve
pre-revocation rows, revoke in the live process, then hypothetically restore the
old verifier/revoked/grant values while keeping that process's original witness,
scope and unexpired clocks. `_validate` has no independent revocation revision to
distinguish those rows from the original permitted state. This is the explicitly
unsupported live-restore case, not evidence of a bypass in the qualified fresh
laboratory flow. An actual reproducer must be labeled a controlled rollback
intervention, never normal lifecycle admission.

## Options and tradeoffs

1. **Retire on every restart/restore (recommended current policy).** No adoption
   of restored credentials or authority rows. Keep Core business-data recovery
   separate from connector authorization. Any future enrollment is explicit and
   newly scoped, never triggered by a backup or manifest. Lowest persistence
   burden; loses connector continuity and requires operator action. It does not
   protect a process plus witness restored together without a trusted restart
   boundary.
2. **Independent durable lifecycle witness (defer).** An external authority
   retains a monotonic installation epoch and terminal revocation/policy
   revisions outside the restored DB's failure domain. Reads must consult a
   current authoritative witness or a rigorously fenced admission lease; no
   cached positive permission during outage. This adds availability, operator,
   retention, multi-resource atomicity and trusted-time questions. Merely using
   another table, another file on the same snapshot, a signed old receipt, or a
   second DB that can be rolled back together is insufficient.
3. **Manual quarantine and re-enrollment after recovery.** Restore business data
   while connector authority remains closed; separately reviewed operator action
   creates a new epoch/installation and credentials only after reconciliation.
   This can be a future operational choice, not a present admin capability or
   permission to persist secrets. It needs a trustworthy quarantine/recovery
   boundary outside the restored image and explicit handling of old projections.

For option 2, a proposed non-secret witness record would minimally bind immutable
installation/organization identity, current dataset incarnation, lifecycle epoch,
policy revision and terminal state. Do not choose a vendor, persist this record,
add a signing key or promise availability in this slice. A restore epoch alone
cannot preserve a revocation if that revocation and the epoch can both roll back.

## Threat and failure matrix

| Event                                                 | Required outcome / test                                                                                                                                                    | Claim boundary                                                                                                                                                    |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Old snapshot contains revoked credential              | Old generation never becomes admissible after acknowledged revoke. Compare retained external terminal state against restored rows; refuse mismatch.                        | Current live-restore case is unsupported; next model must expose it rather than report it already solved.                                                         |
| External witness rolled back with DB                  | Refuse if independent freshness evidence detects rollback; otherwise explicitly outside the trust model.                                                                   | No wholly co-restored mechanism can establish that a later revocation happened. Signing stale state does not establish freshness.                                 |
| Witness absent, unavailable or ambiguous              | Closed admission; no fallback to DB, manifest, expired receipt or cached allow.                                                                                            | Availability loss is deliberate. Cleanup must still run and report uncertainty separately.                                                                        |
| Reset, restart or A→B→A installation switch           | New run/epoch cannot accept old credentials, deadlines or projection results. Never reset revision to an adoptable default.                                                | Restart rejection is current; durable epoch continuity is deferred.                                                                                               |
| Multiple surviving API workers or split-brain restore | Quiesce and fence every old worker before any new admission; an unreachable worker is not proof of retirement.                                                             | Current single-process witness/local barrier is not a multi-worker coordination protocol. A future witness must participate in every admission, not only startup. |
| Stale query or projection completes after retirement  | Do not display it as current or populate the new binding. Bind result acceptance to the initiating scope/epoch.                                                            | Already authorized response bytes may still arrive; no retroactive recall claim.                                                                                  |
| Concurrent read and revoke                            | Revoke committed before the admission barrier refuses read; read holding barrier may finish before revoke acknowledgement. No later read admitted with revoked credential. | Preserve existing materialize-before-release semantics and bounded locks; external witness participation must not introduce a check/use gap.                      |
| Crash between witness change and DB/audit change      | No success acknowledgement until required records durably agree. Incomplete transition is quarantined, never rolled back to allow.                                         | No cross-system atomicity assumed. A witness-first terminal denial may sacrifice availability; reconciliation is a separate design requirement.                   |
| Clock rollback, jump, restart or suspension           | Fail closed on invalid evidence; never recreate a fresh lifetime from old expiry.                                                                                          | Time limits exposure, not historical revocation proof. No portable persisted monotonic timestamp claim.                                                           |
| Grant reduction, disable, rotation                    | Snapshot cannot restore an earlier wider policy or verifier; no overlap or silent grant expansion.                                                                         | Disable, revoke and purge remain distinct operations; they do not delete Core data.                                                                               |
| Cleanup fails or process survives                     | Admission retired independently; retain honest disposal failure and bounded external reap requirements.                                                                    | Absence evidence is attempt-specific, not erasure or a durable revocation ledger.                                                                                 |

## Optional synthetic slice after a continuity decision

Do not implement this model automatically. If the user chooses disposable
re-enrollment, record that policy and retain the current unsupported-restore
boundary; no new witness abstraction is necessary. If the user requires durable
continuity, first select the intended trust and recovery protocol. Only where
its assumptions need validation, propose a bounded test-only reference lifecycle
model and adversarial tests, using public symbolic credential identifiers, not generated
credentials, real PostgreSQL, listeners, keys or new persistent storage. Reuse
existing actual authority tests only where they already operate in the approved
synthetic test composition; do not introduce a general restore endpoint.

1. Specify a small state machine: active → retiring → retired; uncertain witness
   or transition → unavailable. Only separately approved fresh enrollment may
   create a different active epoch. There is no retired → active shortcut.
2. Separate mutable database snapshot state from a model witness object that a
   restore operation cannot silently overwrite. The harness controls rollback
   explicitly. State that this is a model of an assumed independent witness,
   not evidence that such infrastructure exists.
3. Enumerate bounded event interleavings: snapshot, read admission/materialize,
   revoke/reduce/disable/rotate, DB restore, witness loss/rollback, crash at each
   transition boundary, restart, and cleanup failure. Assert denial after an
   acknowledged terminal transition for every subsequent admission. Include a
   negative-control model with both state copies restored: it must demonstrate
   the impossibility boundary, not be counted as a passing security mechanism.
4. Compare model semantics with current authority tests: preserve canonical lock
   order, exact tenant/location/incarnation/generation, immutable run deadline,
   audit failure behavior and already-authorized read limitation. A modeled
   terminal denial is not a proof of actual PostgreSQL concurrent behavior.
5. Produce a small gap report and a proposed operator decision. Stop before an
   external witness adapter, file/database persistence, credential issuance,
   network runtime or production management interface. Do not promote a model
   pass to M2/M3/M4 completion or SDK qualification.

Acceptance for that future local slice is executable counterexamples and bounded
state-machine invariants, with explicit assumptions and no authority side
effects. Actual durable restore qualification would later require the selected
real witness, its rollback/recovery policy, actual database restoration, crash
interruption and independent disposal evidence under a new approved plan.

## Decisions and stopping boundary

This document may be reviewed now. First obtain the product-policy decision on
continuity versus fresh enrollment. Only if it establishes a concrete need for
a new protocol should a future implementation plan be proposed; a model is an
optional validation aid, not a required deliverable or an automatic next task.
Before implementing that chosen slice, confirm its exact scope and plan. The
user has not authorized new persistent connector access or storage through this
proposal. Separate decisions are required for:

- Whether restart/restore must retain connectivity at all, or explicit fresh
  enrollment is acceptable; exact installation and dataset-incarnation meaning.
- Who may enroll, retire, restore and re-enroll; precise capabilities, audit and
  recovery approvals, without inheriting human Owner/wildcard authority.
- If durable continuity is wanted, which independent witness is trusted, who
  can roll it back, how outages fail closed, retention/deletion rules and how
  authority loss is recovered without restoring revoked access.
- Credential lifetime/rotation, delivery and retention, new resource/mount or
  network access, and each security-sensitive issuance/execution action.
- Separate publication, hosted execution, deployment and merge authority.

No code, credentials, persistent witness or runtime resources are created by
this document. Current evidence remains the bounded fifth synthetic laboratory
receipt plus source/tests, not production lifecycle or durable restore safety.

## Normative references

- [Original M2 design, especially §§4–7](2026-11-02-m2-synthetic-laboratory-design.md).
- [Compatible modules: authority, lifecycle and M2–M4 gates](../../08-open-source/2026-10-27-compatible-modules.md).
- [Master Agent Loop](../../10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md).
- [Product coverage and its evidence boundary](../../10-spec-development/2026-11-02-product-description-alignment.md).

Source references above are symbols in the inspected commit; tests were read,
not rerun for this design-only task. No fresh runtime or external state inspection
is implied by the retained fifth-run evidence.
