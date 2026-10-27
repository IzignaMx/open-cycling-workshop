# PR #59 postmerge reconciliation · 2026-10-27

Status: verified for the named merged source; V0.1 remains partial. This record
closes stale hosted-evidence and integration wording, not physical, installation,
capacity or quote activation gates. A successor source requires its own checks.

## Integrated source and terminal evidence

PR #58 merged as `9e5bea10ec041682e63d04e3bb2d2a484a3a6196`.
[PR #59](https://github.com/IzignaMx/open-cycling-workshop/pull/59) merged as
`a9e161f7fdcb986828f85a59c46a5a47015c7b34`, tree
`f1258947a0ad4f8b4d9fd2592b1d99b962487de8`, identical to reviewed PR59 head
`54a2d31b5c730703c6c76f0ef8c44e6be2d630cd`. Live main and run metadata were
rechecked on October 27. The completed independent artifact reviews are recorded
in PR59; this reconciliation preserves their exact-source results and hashes.

[Postmerge CI 40428504739](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40428504739),
attempt 1, completed successfully on that main commit:

- Aggregate **27/27**; exhaustive Python collection **4,727**, **4,669 passed**,
  **58 exact expected skips**, zero failed/error/unexpected skip/unrun.
- All **six mandatory restores** passed setup/call/teardown, including retained
  corrupt-effect refusal before recovery rotation and fresh same-ID replay.
- Both serial shards passed primary and independent manifest-owned absence,
  exact ordered/disjoint inventory, source/image/nonces and B predecessor proof.
- Direct and aggregate browsers each **86/86**, each case one passed result with
  retry 0, no flakes or skips. Repetitions **20 + 9 + 5 + 10** were clean.
- [Security 40428504760](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40428504760),
  [containment 40428504814](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40428504814)
  and [runtime 40428504756](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40428504756)
  passed. Runtime retained eleven checks, three restarts, authentication/branding
  recovery, native ARM64 decoder and three builds. PR59 exact-head DCO passed.
- [Optional QEMU 40428504740](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40428504740)
  failed **NON-QUALIFYING**; native ARM64 is not physical Raspberry Pi acceptance.

| Postmerge artifact      | ID          | ZIP SHA-256                                                        |
| ----------------------- | ----------- | ------------------------------------------------------------------ |
| Full Python             | 12701517641 | `9fbbe77a04ca6c3e182486be8a512598d133b8db7dc116ff7877d7a08acab961` |
| Aggregate qualification | 12702237351 | `7435f2791bcaaeb6e205b3330dcc5fadbb54a817b5b574e9597be4da577376a3` |
| Aggregate browser       | 12702576959 | `95d073fba4daaae1ce8d738fbf76110056d2f38cc3621b42bf6889ffbd43125e` |

The one authorized PR59 candidate validation, CI 40423634750, and ordinary
postmerge checks completed; they are not an outstanding retry/merge queue.
PR58 postmerge CI 40396434262 and earlier PR59 failures remain failed. Historical
CI 40249194704 owned-container absence and original Docker delay remain unknown.
New successful cleanup does not retroactively repair those observations.

## Closed scope and remaining work

The merged source qualifies complete retained-history validation before recovery
rotation, the genuine legacy-0011 fixture, owned cleanup/native matcher and
branding readiness regressions, and the approved canary-only 15-second allowance.
Canary creation remains inside the same 65-second setup; database/worker/default
controls remain 5 seconds. Each Python shard remains 900 seconds/768 MiB, PostgreSQL
1 GiB memory/512 MiB data, and the job remains 55 minutes. No limit, skip, restore,
safety, ownership or retry relaxation follows from this record.

Next bounded Tasks 5/8 work is ingress/enrollment serialization and fresh authority/
grant-adoption fences: every legacy HTTP/sync/order-linked inventory writer must
serialize with enrollment and fail closed for linked orders. No quote API/UI is
activated by selecting that implementation prerequisite. Transport/cancellation,
capacity/latency, old-writer adoption and endpoint exposure retain their own gates.

R01-T035 Windows/Android, physical laptop/Pi and manual accessibility remain
blocked pending operator evidence. Real-installation inventory, isolated physical
corruption and actual-volume restore/RPO/RTO remain separate from synthetic
restores. Preserve browser journals, original history and verified backup. No
installation, deployment or reopening occurred; future PR merge needs specific
approval. Consumed capacity trials are not reopened.
