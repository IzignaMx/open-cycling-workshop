# Current source checkpoint and bounded traceability · 2026-11-01

Status: **V0.1 partial**. This reconciles navigation and task identity;
it does not qualify its own changed source or declare a release.

## Reconstruction and evidence provenance

A second environment replacement on November2 lost the November1 candidate,
worktree/bundle and local logs. This is a same-scope reconstruction on unchanged
remote main, not byte-identical recovery. The November1 filename preserves the
authorized package identity, not its creation time or bytes. No earlier local pass
qualifies these files; fresh RED/GREEN, independent review and hosted evidence are
required. Parent owns authorized publication; merge remains conditional on evidence.

Accepted baseline main: `cdb44aac572df65489fb95a15c0a813cd5445d95`, tree
`abff5e9e9bd75fe17e5ece00327c63ba0a9485c8` (merged PR77).
The [PR77 acceptance record](https://github.com/IzignaMx/open-cycling-workshop/pull/77)
was read on November1 and retained in the session. It reports prior independent
exact-source artifact review; this reconstruction did not redownload/revalidate
those archives or rerun their workflows.

- Candidate `4fe8f19c46718ee91d7ac1681f6b5fb656fdebbf`: CI41221990616,
  Security41221990702, DCO41221990632, micro41221990579, runtime41221990643.
- Fresh main [CI41225378078](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41225378078),
  aggregate artifact13052328859: 27/27 controls; Python5,550 passed +58 expected
  skips =5,608 collected, no errors/unrun; core1,021 and API client1.
- Direct/aggregate browser101 each, repetitions20/9/5/10 and kernel14, no retries.
- Runtime41225378046:11 checks, three restarts, native ARM64 and three image builds.
  Micro41225378075: both workloads and four cleanup observations accepted.
  Python paired cleanup receipts verified absence. Security41225378090: zero findings.

These receipts supersede pending source-qualification wording for PR76/PR77 and
the PR75 candidate, not historical failures. No later pass establishes the cause
or owned-resource absence of micro run41011497919: historical cleanup is **UNKNOWN**.
Ownership40927223929 is spent; PR51/PR56 trials are not replayable.

## Current boundaries and next work

T1–T8 remain pending on both physical devices. R01-T035 remains blocked for physical
Windows/Android storage/device evidence; desktop100k evidence is historical and
not a substitute. Installation, trusted LAN access, recovery, accessibility and
quote capacity/activation have separate gates. October31's safe protocol is
preparation, not physical execution or permission for infrastructure changes.

Full-history pre-reopen validation already has PR59 source-qualified evidence;
actual-installation inventory/recovery and activation remain separate. Do not
reimplement that validator from stale PR58 next-step wording.

Static Pages remains bound to `3c6513d685fe659816bd3ddb47dab91003d3a787`;
no redeployment occurs here. README PNGs are historical captures from `a960bdd`,
not current-runtime proof. Next: qualify the reconstructed documentation/capture
package, then select ready V0.1 correctness work without bypassing manual gates.
Capture lifetime across unmount/reconnect/reload is not established by mounted
edit-revision protection; durable draft/intent ownership needs its separate design.

## Plan-local versus canonical task identity

The August31 workshop plan's numbered steps were incorrectly stored as canonical
R02 IDs. Historical receipts now use **W02-I1-T001–T010** for that plan only.
This correction grants no new completion or evidence.

| Plan-local steps                                            | Canonical relationship                     | Unproven remainder                                             |
| ----------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- |
| T001 bicycle domain/repository                              | R02-T002, partial                          | Full attributes/custom fields acceptance                       |
| T002 state machine/timeline                                 | R02-T004 and R02-T013, partial             | Full canonical aggregate and audit acceptance                  |
| T003 migration; T004 sync; T005 REST; T006 feed; T007 Dexie | Shared prerequisites, not one-to-one tasks | No passport, photos, diagnosis or estimate completion inferred |
| T008 intake                                                 | R02-T005, partial                          | Complete reception acceptance                                  |
| T009 board                                                  | R02-T016, partial                          | Complete canonical UI acceptance                               |
| T010 offline lifecycle                                      | R02-T018, partial                          | Full merge-policy and physical multidispositivo acceptance     |

This history does not complete canonical R02-T001 Customers CRUD, R02-T003 Passport,
R02-T006 photos, R02-T007 diagnosis, R02-T008 estimates, R02-T009 authorization or
R02-T010 repair task list. Later prerequisites require their own scoped mapping.

[traceability.csv](traceability.csv) is a bounded just-in-time ledger, not complete
product coverage. `test_id` identifies a relevant existing test file, not proof all
canonical acceptance criteria passed. V0.2 rows remain partial. R01-T035's
documentation contract is expressly not a benchmark/device test.

## License omission

R01-T002 was absent from the inventory, not the repository. Fresh inspection finds
`LICENSE` and `LICENSES/AGPL-3.0-only.txt` byte-identical GNU Affero GPL v3 texts;
`REUSE.toml` declares AGPL-3.0-only. The repository contract requires hosted
`reuse lint`; retained baseline Security supplies prior source evidence.
This is bookkeeping, not a licensing change or legal acceptance.

## Fresh local evidence

Six reconstructed contracts first failed against unchanged baseline documentation
for the missing checkpoint, false canonical IDs, absent ledger, stale README and
checklist, and omitted task. See the [implementation plan](../superpowers/plans/2026-11-01-documentation-reconciliation.md)
for fresh command results. No pre-replacement local result is inherited.
