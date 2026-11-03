# PR83 bounded M2 laboratory acceptance and fresh-main reconciliation

## Immutable source and provenance

PR83 was merged under the separate 2026-11-03 14:42 approval. Accepted main is
`35f88e0f2a9a9e7b0f0dece03498cc6265205b91`, tree
`106e11df74b4e656c4b6227610648b3466c3e436`. Its parents are
`e9c11ad11a564c80add99f4dc901ffe2d583c8e6` and published PR head
`b1d3b015703c45620f3a65d155520f240904b5be`. Local equivalent
`b5db35bd2bbb39848ce408e86ee31f9e4c00dffc` has the same tree.
See [merged PR83](https://github.com/IzignaMx/open-cycling-workshop/pull/83) and
[immutable main source](https://github.com/IzignaMx/open-cycling-workshop/commit/35f88e0f2a9a9e7b0f0dece03498cc6265205b91).

The `artifacts/` paths below identify retained review files in the coordinator's
archive, not tracked repository files or public GitHub paths. Availability depends
on that retained archive; the public run links identify the original executions.

This document reconciles retained, independently reviewed evidence. It is not a
new execution, production access approval or a claim that historical source files
already contained later results. Earlier source-pending fields remain historical.
The bounded laboratory plan is complete; full M2 remains incomplete. A proposed
[lifecycle/restore design](../superpowers/specs/2026-11-03-m2-lifecycle-restore-proposal.md)
is a next proposal requiring review and decisions. It has no implementation approval
and is not active production implementation.

## Fifth synthetic laboratory: same-tree qualification

The separately authorized [fifth M2 run41568644741](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41568644741)
ran attempt1 on PR test merge `40740e51b1d24d04af49479b24d2eb0d01483d24`,
not on the later main commit. Its tree exactly matches accepted main. The retained
independent review accepts **19 checks**, all **16 supervisor milestones**, and
**13 API checks**, with a validated stopped API and `database_cleanup_complete`.
The independent cleanup receipt verifies owned containers absent and root removed
for this attempt. API self-report and supervisor/cleanup observations stay distinct.

- Job125696123867; artifact13200515969: 944 ZIP bytes, 1682 evidence bytes.
- Artifact SHA256: `0b8dbce6305ca2fcf98375f0b38656cfa3771a95e979f32f55ff4160d9272096`.
- Retained reviewer receipt: `artifacts/m2-hosted/hosted-independent/fifth/final-review.json`.
- Receipt SHA256: `cabae2c7b36dff39d32b2a70c5e52b35aa10466e864ca6fcc2e74a529fc01f58`.

The review's then-pending ordinary-CI and merge-authority notes are historical and
superseded by the separately approved merge and fresh-main evidence below. Its
limits are not erased. Five permits were consumed; **no sixth** M2 run was authorized
or executed. The M2 workflow does not run on main push. Same-tree fifth-run evidence
is not described as a fresh-main M2 rerun.

## Fresh-main ordinary qualification

[CI41656497568](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41656497568)
completed both jobs successfully on main35f88e0f, attempt1: **27/27 controls**,
**5971 Python passes +58 exact intentional skips**, **1237 frontend** and **1 API
client** pass. Python job125988094010 and verify job125999241561 were checked
independently. No failure, error, unexpected skip or unrun Python case was accepted.

- Full-Python artifact13239559754: 784908 bytes; SHA256
  `b555bf1aada493bebabdd900823a5d296ed54c55667c79f2402774c1ad5adfe0`.
- Canonical pair validation used independent job-log nonces/image identities,
  source seals against the exact tree, complete ordered disjoint shard inventory,
  containment, predecessor-cleanup binding and both independent cleanup receipts.
  Shard A: 3818 passes +11 skips. Shard B: 2153 passes +47 skips.
- Aggregate artifact13246160652: 4475 bytes; SHA256
  `2997aafa6be6e674d813560c62c35778b629cfc46d1b91efcf6a1054515fafd0`.
- Browser counts: **126 direct** from terminal job log, **126 aggregate** from
  qualification JSON. Small source-bound reports show repeats **20/9/5/10** and
  **kernel 14**, each with exactly one passing result and retry0.
- Eight small artifacts were downloaded and byte/hash/source verified. Inventory
  has43 PostgreSQL cases and2 edge cases; branding has2 distinct restore cases,
  each checking3 profiles. Branding explicitly excludes whole-application smoke
  and pending-client recovery qualification.

The direct/qualification browser ZIPs (332515058 and332503367 bytes) were **not downloaded**. There is no archive-byte, full-report retry, trace or screenshot
verification for those large archives. No retry markers were observed in the job
log; that observation is not equivalent to inspecting every large-report result.

[Runtime41656497424](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41656497424),
[security41656497803](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41656497803)
and [microfixture41656497409](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41656497409)
were independently accepted on the same main source, attempt1. Runtime: six jobs,
11 checks, three restart cycles; native ARM decoder source checked, not physical
Raspberry Pi acceptance. Security:41 active/43 locked packages, zero findings.
Microfixture/record receipts and four diagnostic leaves verify current owned
resource absence; neither is maximum-capacity qualification.

Final ordinary receipt: `artifacts/m2-hosted/pr83-postmerge/ordinary/final/review.json`.
SHA256: `3d2f9274ce2df1ee5638b4b0f7bc548d2c567729a1164a10f4a6fdafd5167463`.
The adjacent Python receipt, terminal metadata, small ZIPs and validator scripts
retain the independently checked evidence. This is new main evidence, not prior
PR CI relabelled as main.

## Preserved history and remaining gates

First through fourth hosted failures remain failures. The first has a known
image-preparation/BuildKit boundary failure. The second, third and fourth hosted
causes remain UNKNOWN; offline certificate reproduction does not identify a purged
hosted certificate. Cleanup for the first and second attempts remains unproven.
Third/fourth/fifth cleanup evidence applies only to each matching attempt and is
**not secure erasure** or full-crash recovery proof.

M2 contributes only a bounded synthetic prerequisite to FR-PLG-003/004/005/008/009
and SEC-002/003/005/006/007/010. R09-T020 and R10-T014 remain incomplete: no generic
SDK, registry, loader, operational connector or production machine-identity rollout
is accepted. Operator provisioning, grants, expiry/rotation/revocation lifecycle,
installation incarnation/restore fence and operational retention need their own
specified decisions and evidence before production implementation.

V0.1 remains partial. T1–T8 and R01-T035 physical acceptance, complete installation,
recovery and maximum-capacity gates remain open. SPENT40927223929 cannot be repeated;
historical UNKNOWN41011497919 is unchanged. Pages is unchanged. This reconciliation
creates no new execution permission, no V0.2 admission and no whole-project completion.
