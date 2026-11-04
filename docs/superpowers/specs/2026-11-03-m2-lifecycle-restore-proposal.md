# M2 lifecycle and restore: bounded anti-resurrection proposal

2026-11-03. **Selected lifecycle policy; documentation only.**
Accepted baseline: main `c0fe501a9f93393c106c49aece4a27af495b79e9`, tree
`bbb9b6e4d140c96df54ee18ac4890f64a4a4be51`. The inspected local commit
`062f881093527da55e2419d9b70268957632c26a` has that same tree, as recorded
in the retained PR84 postmerge review. The earlier inventory at
`b5db35bd2bbb39848ce408e86ee31f9e4c00dffc` (tree
`106e11df74b4e656c4b6227610648b3466c3e436`) is historical; its laboratory
implementation was rechecked against the accepted baseline for this decision.
No production machine authority, persistent credential/storage service, runtime
execution, publication or merge is authorized or implemented by this document.

## Decision record and recommendation

On November 3 the maintainer delegated the lifecycle policy decision. The
selected policy is **explicit fresh connector enrollment after database
restore**, minimizing recovery complexity without
silently reviving restored credentials. Automatic identity continuity through a
new durable external witness is not selected.

**Ordinary service restart is not database restoration.** Restart alone must not
become a destructive re-enrollment trigger or rotate the dataset incarnation.
For a future production connector, restart continuity should preserve an
otherwise current authorized installation, subject to current grants, expiry and
revocation. That is a requirement for future machine-authority design, not an
implemented production capability. The disposable laboratory intentionally has a
stricter boundary: each API process has a fresh run witness, so its old laboratory
credentials cannot survive restart. Do not copy that laboratory policy into
ordinary production restart handling.

No new executable guard or state-machine abstraction is needed now: production
has no connector machine principal to extend, and the laboratory already refuses
existing/restored database adoption. The useful increment is this explicit
contract, grounded in existing recovery and session code. An external durable
anti-resurrection promise cannot be built entirely from values inside the same
restored database or backup.

## Source-backed restart and restoration distinction

- `services/platform/src/cycling_workshop/identity/domain.py::Principal` is a
  human user principal; `identity/security.py::SessionTokenService` issues tokens
  with session version and optional dataset incarnation. It is not a machine
  identity interface. `cycling_workshop/app.py::create_app` configures token
  validation from the configured authentication secret.
- `identity/dependencies.py::principal_from_request` and `effective_principal`
  recheck current organization incarnation, active account/session version and
  capability intersection. With unchanged secret, DB state and valid lifetime,
  recreating the service does not itself invalidate a human session. This is
  source behavior, not a newly executed restart qualification or a promise that
  human sessions should be reused by connectors.
- `identity/cutover.py::lock_compatibility` and `validate_incarnation` provide the
  current compatibility barrier. `identity/cutover_cli.py::recover_cutover` /
  `_change` require an exact expected incarnation and active cutover, validate
  recovered quote history, generate a fresh incarnation, append an audit event
  and commit together. Ordinary startup does not invoke this recovery operation.
- `scripts/database/backup_postgres.py::restore_backup_bundle` accepts an
  explicitly confirmed isolated empty target and verifies matching schema,
  version and restored metadata. Its advisory lock coordinates that tool's
  invocations, **not arbitrary live clients**. It does not itself rotate
  incarnation or prove that the operator has stopped all writers.
- `services/platform/tests/identity/test_cutover_http.py::test_rotation_does_not_collide_with_restored_session_counter`
  and `test_cutover_postgres.py::test_restore_counter_collision_rotates_before_all_authenticated_paths`
  cover rejection of prior sessions despite restored/colliding session counters
  after incarnation rotation. These tests concern human admission, not absent
  production machine credentials.
- `tests/labs/m2/authority.py::LabAuthority.__init__` creates the process-local
  run witness. `runtime_authority.py::PostgresLabAuthority._build_engine` refuses
  an existing database. Existing M2 tests
  `test_new_run_never_accepts_old_credential_and_close_is_terminal` and
  `test_restored_old_database_rows_do_not_reconstruct_external_run_witness`
  support disposable-run refusal, not persistent restart continuity.

## Selected recovery sequence and low-friction limits

1. Quiesce all old API/worker/connector admissions and isolate the restore target;
   an unreachable or surviving worker is not evidence of quiescence. Never use
   live database rollback as a supported shortcut.
2. Restore into an isolated empty target and perform the accepted data/schema/
   integrity checks. Keep it unavailable on uncertainty. Follow the existing
   [backup and recovery procedure](../../07-operations/2026-10-14-backup-restore.md),
   including its exact-incarnation recovery precondition before reopening.
3. Perform the audited incarnation rotation for the restored organization before
   accepting requests under that recovered authority. Do not rotate unrelated
   organizations or treat a process restart as a recovery event.
4. Keep future connector authority unavailable until separately authorized fresh
   enrollment binds the recovered incarnation, exact installation/organization/
   location and explicit current grants. Never reconstruct authorization from
   restored verifiers, old credential files, cached grants or an old manifest.
   Existing production has no such enrollment endpoint; this step is a future
   lifecycle requirement, not a runnable instruction to mint credentials now.
5. To reduce operator friction, eligible non-secret descriptive configuration may
   be offered for review. Configuration is not authority: permission requests,
   endpoint destinations and identity bindings require current validation, and
   secrets/previous approval are not carried forward by the configuration copy.
   Do not delete Core business data as part of module re-enrollment.
6. Dispose or quarantine old connector projections according to an explicitly
   defined future retention policy. Do not label restored/stale projection data
   as current. Offline/unavailable means no current fetch and no queued privileged
   admission, automatic refresh, replay or speculative success.

This sequence relies on the supported operator-controlled recovery boundary. It
is not a new automatic detector for privileged DB rollback, restoration of the
whole process plus its witness, or split-brain workers. Those remain outside the
laboratory guarantee. The immediate stopping point is reviewed documentation;
no persistent access, storage, credential or production management surface is
created to implement these future requirements.

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

## Historical alternatives and current tradeoffs

1. **Retire on every laboratory restart/restore (existing lab policy only).** No adoption
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

Rows concerning an external witness describe the deferred alternative and its
limits, not a new dependency of the selected re-enrollment policy.

| Event                                                    | Required outcome / test                                                                                                                                                                    | Claim boundary                                                                                                                                                    |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Old snapshot contains revoked credential                 | Old generation never becomes admissible after acknowledged revoke. Keep restored authority closed; require fresh enrollment after recovery. An external witness is a deferred alternative. | Current live restore is unsupported; no model or external witness is being implemented.                                                                           |
| External witness rolled back with DB                     | Refuse if independent freshness evidence detects rollback; otherwise explicitly outside the trust model.                                                                                   | No wholly co-restored mechanism can establish that a later revocation happened. Signing stale state does not establish freshness.                                 |
| Witness absent, unavailable or ambiguous                 | Closed admission; no fallback to DB, manifest, expired receipt or cached allow.                                                                                                            | Availability loss is deliberate. Cleanup must still run and report uncertainty separately.                                                                        |
| Lab reset/restart, recovery or A→B→A installation switch | New run/epoch cannot accept old credentials, deadlines or projection results. Never reset revision to an adoptable default.                                                                | Lab restart rejection is current; ordinary production restart alone is not an incarnation change.                                                                 |
| Multiple surviving API workers or split-brain restore    | Quiesce and fence every old worker before any new admission; an unreachable worker is not proof of retirement.                                                                             | Current single-process witness/local barrier is not a multi-worker coordination protocol. A future witness must participate in every admission, not only startup. |
| Stale query or projection completes after retirement     | Do not display it as current or populate the new binding. Bind result acceptance to the initiating scope/epoch.                                                                            | Already authorized response bytes may still arrive; no retroactive recall claim.                                                                                  |
| Concurrent read and revoke                               | Revoke committed before the admission barrier refuses read; read holding barrier may finish before revoke acknowledgement. No later read admitted with revoked credential.                 | Preserve existing materialize-before-release semantics and bounded locks; external witness participation must not introduce a check/use gap.                      |
| Crash between witness change and DB/audit change         | No success acknowledgement until required records durably agree. Incomplete transition is quarantined, never rolled back to allow.                                                         | No cross-system atomicity assumed. A witness-first terminal denial may sacrifice availability; reconciliation is a separate design requirement.                   |
| Clock rollback, jump, restart or suspension              | Fail closed on invalid evidence; never recreate a fresh lifetime from old expiry.                                                                                                          | Time limits exposure, not historical revocation proof. No portable persisted monotonic timestamp claim.                                                           |
| Grant reduction, disable, rotation                       | Snapshot cannot restore an earlier wider policy or verifier; no overlap or silent grant expansion.                                                                                         | Disable, revoke and purge remain distinct operations; they do not delete Core data.                                                                               |
| Cleanup fails or process survives                        | Admission retired independently; retain honest disposal failure and bounded external reap requirements.                                                                                    | Absence evidence is attempt-specific, not erasure or a durable revocation ledger.                                                                                 |

## Deferred optional protocol model, not a current task

The selected re-enrollment policy does not require this model or a new witness
abstraction. The following remains historical design exploration only. If a
future explicit decision instead requires durable continuity across restoration,
first select the intended trust and recovery protocol. Only where
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

The delegated product-policy choice is recorded above: fresh enrollment after
restore, not destructive re-enrollment on ordinary restart. No further product
preference question is needed for this documentation increment. A new protocol
or model is not an automatic next task. Future production machine-authority
implementation still needs its own concrete design and permission boundaries.
Before implementing that chosen slice, confirm its exact scope and plan. The
user has not authorized new persistent connector access or storage through this
proposal. Separate decisions are required for:

- How future ordinary restart continuity will be implemented while restore
  requires fresh enrollment; exact installation and dataset-incarnation meaning.
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

Historical human-session/recovery tests above were read, not rerun during this
document refinement. The accompanying local characterization in
`tests/labs/m2/test_runtime_authority.py` adds 11 cases and reports 29 passing
cases total, using actual bootstrap control flow with fake SQL/engine inputs.
The retained local result is
`artifacts/m2-lifecycle-policy/bootstrap-characterization-final.log`; this is
not a tracked public evidence file. No PostgreSQL, credentials, TLS or runtime
resources were created by those cases, and they do not prove native restore
behavior. This test path is included by the M2 workflow, so publication that
triggers that workflow requires a separately approved sixth laboratory run.
Local test scope implies no publication or execution permission. No fresh
runtime inspection is implied by the retained fifth-run evidence.
