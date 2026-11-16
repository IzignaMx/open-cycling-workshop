# Synthetic origin isolation and artifact admission rehearsal

## Baseline and useful next proof

Baseline main is `2c083030fbf83285d0a46ea8f56531fa2aca5172`, tree
`2b3e3df280b4e90be6f4bc0060bed64914c0fd48`. The coordinator reports
[CI 43762175591](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/43762175591)
qualified PR109 main. That is baseline evidence, not qualification of this increment.
Dated earlier pending checkpoints remain historical records.

Reload, graceful restart and injected crash after inert staging already have
separate scenarios. Repeating them does not choose a safe transition. This increment
instead combines the actual historical and current App/SW in the same browser context,
on distinct disposable loopback origins, with an executable artifact-admission policy.
It is an independent OFF-007/recovery prerequisite under the Master Loop, not a claim
that physical V0.1 or workshop activation gates have been completed.

## Artifact policy and tested boundary

The synthetic host accepts a separately selected exact build receipt: commit, tree,
lock, database and the complete asset map. The receipt is produced by the archived
build outside its proposed serving directory and checked against the checkout.
It is trusted test input, not a release-signing or remote-attestation system.
Candidate directories and the filesystem are generated and controlled by the test runner.
This synchronous loader follows filesystem links and does not bound candidate file sizes;
it is not an untrusted-upload parser or protection against hostile symlinks, FIFOs or
resource exhaustion. Hash checks constrain admitted response bytes, not arbitrary reads
against a hostile filesystem. Production use would require its own threat model.
A candidate directory's self-consistent manifest is insufficient authority.

Before listening or replacing its admitted distribution, the host verifies all
identity fields, asset membership, lengths and hashes, then retains an immutable snapshot
of the validated bytes. Request handling serves that snapshot, not mutable files.
A failed replacement cannot change the previously admitted distribution. Historical,
mixed, missing or corrupt assets and a forged directory manifest are rejected.
Changing disk files after admission cannot change served bytes. Unknown routes,
backend requests and alternate fallback paths remain refused.

This is exact-artifact allowlisting, not a numeric minimum-version comparison or
an inference that every descendant commit is safe. In particular, this test host is
not a production admission mechanism. Existing production hosting, CDN, domain,
service-worker update policy and authentication are unchanged.

## Native rehearsal and causal evidence

One disposable browser context loads the unmodified SHA-pinned cc18a203 App/SW on
origin A and the exact current compatibility-aware App/SW on origin B. Each origin
has the same database name but distinguishable synthetic rows. Both reach the existing
post-maintenance UI barrier before test data is committed. Asset hashes and service
worker control are checked on both origins.

After offline admission, failed uncached network probes establish the offline condition.
Reload A through its installed SW and wait until its expired maintenance witness is
removed. Its known historical future-payload deletion remains an expected counterexample.
Meanwhile B's exact snapshot, journal, checkpoint and original absolute TTL must remain
unchanged. Reload B through its own SW: its maintenance witness must disappear, while
its compatible reader preserves the future bytes and retained journal/checkpoint.
No source rows are imported, submitted, reseeded or deleted as migration work.

An incompatible distribution offered to B must be rejected without replacing the admitted
B snapshot. This proves the test host's rejection behavior and origin separation. It is
not historical same-origin exclusion: an already-cached incompatible shell on B would
not be revoked by a server refusing to serve it later. No such cache is introduced as a
supported rollout path.

## Recommended technical decision and remaining sequence

Recommend a separately reviewed transition ADR for a fresh origin with a strict
compatibility-aware artifact floor, while retaining exact-v1 writes at the existing
origin until that decision is accepted. This is a recommendation, not authorization
for DNS, domains, installation changes or a production rollout. A version flag, path,
database rename, server minimum or forced SW reload cannot replace the origin boundary.

Minimum remaining implementation sequence:

1. **Choose the transition contract (G1).** Name every supported entry point, exact
   admitted and recovery artifacts, origin/partition and rollback floor. Specify whether
   existing unsent work is completed at its source or explicitly transferred; do not
   silently reinterpret an old draft as a new bicycle selection.
2. **Design lossless handover (G3/G4).** Define a concurrent-writer protocol for edits
   committed after a snapshot, ownership/principal/scope/dataset checks, immutable journal
   operation IDs, pending/inflight/unknown outcomes and PROTECTED metadata. A copier alone
   cannot prevent an old offline client from producing later work. No credentials are
   copied. Reauthentication and explicit source/target admission precede private-data use.
3. **Implement and rehearse that protocol before real transfer.** Preserve source bytes,
   absolute TTL and uncertain commands; prove idempotent retry and recovery after partial
   copy, quota abort, interruption and verification failure. Do not duplicate submissions,
   reset expiry or remove source data just because transfer started.
4. **Enforce the chosen artifact floor on every real delivery path (G2/G5).** Qualify
   installation, partial update, old cached tabs/profiles, rollback refusal and compatible
   forward recovery. The synthetic allowlist does not protect an arbitrary CDN/fallback.
5. **Then implement selector persistence and activation (G6).** Add the selected bicycle
   identity with explicit intent/version semantics and recovery tests in the protected
   boundary. Preserve existing read/write authority and invalid-selection refusal. Qualify
   supported platforms and obtain the specific activation decision before enabling writes.

If no transition architecture is approved, keep v1/shared-origin operation and defer the
richer selector. G1–G6 remain open. No production data, selector, new format or deployment
is activated by this increment.

## Qualification status

Native execution is pending. Authoring and collection are not browser execution;
no local browser launch bypasses the earlier restriction. Local negative controls and
source-bound builds will be recorded separately from later hosted native evidence.
The full rollout, handover, privacy and physical-platform gates are not closed by one
synthetic isolation scenario.

Local checks: **1,662 frontend tests**, **213 repository tests**, and **33 focused
admission/host/fixture tests** passed. Types, lint, formatting and production isolation
checks passed; the production PWA and historical archived App build succeeded. The one
new native scenario was collected but not executed. Initial local aggregate attempts
are retained separately: a concurrent frontend invocation interfered with temporary
outputs, and the first aggregate lacked backend workspace dependencies/pinned build
invocation. They are not candidate qualification; corrected serial checks remain separate.
