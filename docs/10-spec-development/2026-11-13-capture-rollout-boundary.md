# Capture reader exclusion and rollback boundary

## Decision, authority and present outcome

Baseline: PR104 main `3c43843d7da0535db53612efbba2e0563b542e40`, tree
`37a8790b3eb68ee011e969638360ce0953cbedcb`. This is a bounded integrity prerequisite
under Master Loop §§5/10/14/16 and OFF-007/R01-T035, not completion of the bicycle
selector or V0.1 physical qualification. Existing traceability statuses remain.

**Today: retain exact v1 production writes in the shared same-origin database.**
The compatibility-aware reader may be distributed without enabling a new payload.
Distribution/merge alone does not establish exclusion of historical readers.
No production runtime, schema, retention, authority, SW or deployment change is
introduced here. No payload deletion is introduced as an upgrade procedure.

The prior reader baseline preserves validated unknown payloads and refuses their
use; it does not revoke old code. A release manifest, operator checkbox or passing
unit test is not an exclusion mechanism. There is no implemented safe same-origin
activation procedure for format >1 while historical offline code can return.
This deliverable makes that limitation executable and specifies evidence needed
before choosing and implementing a transition architecture.

## Why existing controls cannot establish exclusion

- `WorkshopController.start()` runs capture cleanup before session observation.
  `CaptureRecovery.cleanup()` invokes all-content maintenance even without a
  currently admitted user. Authentication revocation and server cutover cannot
  stop an already-installed offline historical client performing local cleanup.
- The exact SHA-pinned `cc18a203` sweeper reads checkpoint/content stores without
  a device owner, ticket, epoch or network check. An unknown payload is rejected
  and deleted even if a separate new reader first preserved it. Its cleanup does
  not consult a newly invented minimum-reader marker.
- `captureWriter` covers the journal sequence, not software identity. Rotating its
  epoch makes the old guarded load fail, but does not fence the historical sweep.
  Do not repurpose this anti-duplicate protection as a binary-version gate.
- Dexie 4.4.4 can reopen v9 with a v8 declaration after versionchange closed the
  previous connection. Closing a connection is not permanent client exclusion.
- PWA autoUpdate/cache cleanup does not replace JavaScript already executing in
  multiple tabs. An offline cached shell need not receive a newer service worker.
  A server minimum version, asset retirement, elapsed TTL or successful update
  notification says nothing about every offline browser/profile able to return.
- A renamed database/store or sidecar is not browser-enforced origin isolation.
  Even if known old code does not open it, authority, orphan cleanup, migration,
  downgrade and old reduced-form submission remain separate proof obligations.

These statements concern normal historical binaries, not malicious JS, extensions,
full profile rollback or arbitrary disk copying. No stronger threat model is claimed.

## Executable evidence and its limits

The existing `capture-format-compatibility.test.mjs` loads unmodified historical
validator/store sources using the fixture's hashes and independent transpilation.
New cases demonstrate:

1. Locked device owner, a different writer epoch and a synthetic reader marker
   each leave historical maintenance able to delete a future payload.
2. A compatible reader preserves/refuses the future draft; after a synthetic v9
   upgrade the v8 database class reopens and historical maintenance still deletes it.
3. Two connections share the same fake-IDB data: newer preservation followed by
   historical maintenance still loses the row. This models storage interleaving,
   **not** a native multiple-tab/service-worker lifecycle test.
4. The exact v1 control remains unchanged and readable after compatible-to-old
   reopen. This is a draft-format control, not blanket old-application compatibility.

Deletion is asserted only inside disposable synthetic test databases to preserve
counterexamples. Passing means the proposed shortcuts remain disproved, never that
rollout is safe. No runtime fix is expected to make the historical binary cooperate.
The new documentation contract was observed failing before this decision existed;
behavioral counterexamples intentionally pass on unchanged production code.

The existing native `legacy-client-upgrade.spec.ts` pins `714342` and the earlier
`ocwp` database/server-floor cutover. It does not qualify the `cc18a203` reader of
`ocwp-authenticated-v1`. Native tests for the latter are still required; no fake
IndexedDB assertion is represented as browser origin or SW evidence.

## Rollout and rollback matrix

| Situation                                                               | Safe action today                                                                          | Required claim boundary                                                                  |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| offline historical client can return                                    | Keep exact v1; retain its work and supported sync contract                                 | No clock, age or server response proves its retirement                                   |
| multiple tabs, old and compatible                                       | Keep v1; preserve guards and avoid forced reload                                           | Closing known tabs or listing current clients is not an exhaustive offline inventory     |
| partial update: new shell/old page or SW, interrupted install           | Keep v1; preserve drafts and journal; retry only ordinary update                           | Do not activate based on one new shell reporting ready                                   |
| compatible reader used, then old cached reader reopens                  | Keep v1; future bytes would still be at risk                                               | A successful earlier compatible load is not permanent exclusion                          |
| compatible reader installed everywhere claimed, but evidence incomplete | Treat activation as blocked                                                                | Inventory/attestation alone is not browser enforcement                                   |
| hypothetical new format already persisted                               | Stop new-format admission without converting existing bytes; use compatible recovery build | Never redeploy pre-baseline JS into that storage context or destructively downgrade data |
| unknown or mixed storage contents during rollback                       | Preserve and block unsupported work; inspect through authorized recovery                   | Do not infer absence from server backup, elapsed TTL or one open tab                     |

For this draft-format boundary only, rollback to pre-PR104 code is compatible
while all actual payloads remain v1. It is not permission to roll back arbitrary
API/schema/authorization changes. Once a future format has been persisted, the
rollback floor must be an exact compatibility-aware artifact qualified against
those actual envelope versions. PR104 is the earliest candidate reader baseline,
not a guarantee for arbitrary future envelope fields or changed lifecycle rules.

If unsupported bytes exist now, they already require a compatible reader and the
existing honest blocked-recovery path. Never create them as a production rollout
probe. The normal authorized lifecycle remains distinct from upgrade procedures;
TTL expiry is not an exclusion proof or a migration plan.

## Future architecture choices: proposed, not approved

A distinct browser origin is the plausible browser-enforced storage boundary,
not a selected deployment decision. Old code running on origin A cannot directly
open origin B's IndexedDB under normal same-origin policy. That alone does not
settle migration, ongoing old-origin writes, privacy or server concurrency.
Changing a URL path, SW scope or database name is not changing origin.

A future ADR must choose and compare:

- Continued shared origin with exact-v1-only writing, deferring the richer draft.
- A new origin whose complete shell/assets/SW/recovery artifacts have a proven
  minimum reader floor. Never serve historical incompatible code at that origin,
  including rollback, CDN fallback, emergency image or offline cache restoration.
- A managed installation boundary only if enforceable binary access restrictions
  can actually be demonstrated for every supported profile. Operator assertions
  and remote revocation alone are insufficient.

No proposal authorizes domain/DNS changes, credential transfers, broad access,
new mandatory online admission or destructive migration. Mandatory online version
checks would change Offline First behavior and need the applicable governance.

## Measurable gates before activation

**G1 — Architecture and artifact identity.** Accepted ADR names the storage/origin
boundary, exact old/new/minimum-reader commits and built asset/SW hashes, all entry
points, rollback artifacts and supported browser/profile classes. A reviewer can
match every tested artifact to deployed candidates. A boolean version flag is not
an acceptable proof artifact.

**G2 — Historical execution exclusion or isolation.** Native rehearsal runs actual
cc18a203 App/SW with no network, against a future candidate in the intended browser
partition. Include already-running historical tabs, restart from old cached shell,
partial update, old profile reopened later, and rollback after compatible use.
For a new origin, demonstrate the browser storage boundary using different actual
origins, plus refusal to serve an incompatible artifact at every new-origin entry
point. Record network traces, exact synthetic rows and artifact identities. Any
historical mutation/deletion of new-format storage is a fail. No fake-IDB origin
simulation or inventory checkbox closes this gate.

**G3 — Lossless handover and crash recovery.** Before copying any real data, specify
and rehearse pending/inflight/unknown journal work, immutable operation IDs,
principal/scope/dataset ownership, protected capture receipts, unsent drafts and
original absolute TTL. A consistent snapshot plus concurrent-writer protocol must
account for edits committed during the handover. Test crash before copy, midway,
after verification, quota abort and retry. No duplicate command, silently reduced
form, orphan pending work or reset TTL is acceptable. Do not automatically submit
or transform unknown outcomes. The current server backup does not contain local
unsent draft/journal bytes. A copy is not a proven restore.

**G4 — Privacy, cleanup and offline continuity.** Specify who may read/import each
private draft and how both origins retain/logout/expire any temporary copies.
No credentials are copied by default, and source data is not removed just because
transfer began. Explicit permission and verified recovery precede any disposal;
failed cleanup must be visible. Test offline operation on supported platforms,
reauthentication and revocation without displaying another principal's data. A new
origin cannot silently read or clean the old origin's private storage.

**G5 — Rollback and forward recovery.** Build and hash the rollback floor, then
rehearse actual future-envelope preservation/refusal, leave cancellation, explicit
cleanup, crash and reconnect using that artifact. Attempting a pre-floor release
must fail before it can access new-format storage; existing device epochs alone
cannot provide this guarantee. Recovery after a format write must preserve its
bytes, pending journal and uncertain outcomes; use a forward fix if necessary.
Server/data restore is a separate, explicitly authorized operation, never an
automatic destructive down migration or return to the old origin with stale work.

**G6 — Source-bound qualification and activation decision.** Tie native results,
restored synthetic exports, compatibility matrix, immutable artifacts and code
review to the same candidate. Full required CI, physical platform and relevant
release gates remain distinct. An authorized release decision names the specific
format, validated envelope and scope only after G1–G5 are satisfied. Missing,
ambiguous, stale or failed evidence keeps future writes/selector blocked.

## Next executable work and acceptance status

Next step is a separately reviewed transition ADR and native cc18a203 App/SW
harness (not the older 714342 fixture), followed by preservation-capable handover
rehearsal. Do not add a production activation switch ahead of those mechanisms.
For a proposed new origin, use synthetic isolated test origins first; real endpoint
or data migration requires its own authorization and evidence.

This decision/test increment has passed local verification and independent review;
G1–G6 and selector implementation remain **blocked**, not partially activated.
The branding timeout, physical V0.1 acceptance, restore/capacity and quote gates are
unchanged. No publication, deployment or operator migration is requested here.

## Candidate qualification

Candidate checks: **1,511 frontend tests passed**, zero failed/skipped; **25 kernel
compatibility tests passed** (including six new counterexamples/controls); **206
repository tests passed**. Lint, prescribed formatting (397 Python files), TypeScript
and mypy (126 files) pass. The documentation contract RED and initial Python
formatting failure are retained alongside corrected passing receipts. Independent
review accepted the bounded claims, pinned fixtures and G1–G6 without blockers.
Final documentation stamping is followed by repository/format checks.

No production source, SW configuration, backend, schema or lockfile changed.
Validation is proportional to this decision/test-only increment: a new aggregate,
full backend suite and native browser run were **not executed**. Strategy delivery
is complete; technical historical-reader exclusion and G1–G6 remain unresolved.

Baseline CI43316263959 qualifies only PR104 main: 10 checks,
27 aggregate, frontend 1,505, Python 6,740 plus 58 expected skips and direct browser
140 with zero retries, as reported by the coordinator. It is not candidate evidence.
