# Full-Python canary create allowance

> **2026-10-27 closure:** merged through PR #59 at `a9e161f`; exact-main
> CI 40428504739 passed 27/27, all 4,727 collected Python cases (4,669 pass /
> 58 expected skips), six restores, both cleanup proofs and retry-free direct/
> aggregate browsers. See [terminal evidence and remaining gates](2026-10-27-pr59-postmerge-reconciliation.md).
> The preparation/pending wording below is historical, not a new run or merge
> authorization. Physical, installation, capacity and activation gates stay open.

Status: independently reviewed; one exact-source hosted validation pending. The user explicitly approved this narrow allowance and discretionary
PR59 merge only if qualification passes. No deployment, installation reopening or
quote activation is included. No retry or second validation is authorized here.

## Preserved failure evidence

The base is PR59 head `3ac17ce16da87f46750b2b2d7af4c03c5d963ae2`, tree
`6b367aed3e30d3f429d2d9c86ded344eb2bbd676` (local snapshot `0cf3db4`).
[CI 40406623072](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40406623072)
failed 24/27: shard A's canary `docker create` hit the five-second command timeout
before collection, recorded `creation_uncertain` and an empty CID file. Both
shards' primary and independent owned-container absence proofs passed. Shard B's
strict receipt selected 2,013 cases, passed 1,966 with 47 expected skips, including
all required service-restore phases. The corrected genuine0011 branding fixture
was not reached by shard A. Direct and aggregate browsers each passed 86/86 with
single retry-zero results, and repetitions 20+9+5+10 were clean. Security, DCO,
containment and runtime/native ARM passed; optional QEMU failed nonqualifying.

Earlier postmerge CI40396434262 similarly failed A's canary creation before
collection with verified cleanup. Initial PR59 CI40401909437 failed a synthetic
schema fixture, later corrected; it remains a failed source-bound checkpoint.
Historical CI40249194704 container absence remains unproven. No new allowance
retroactively changes any failed result, establishes historical cleanup, identifies
Docker's underlying delay or proves fifteen seconds sufficient.

## Exact approved change and unchanged boundaries

Only the full-Python supervisor's **canary** `docker create` call requests fifteen
seconds instead of five. The existing executor still takes the smaller of that
allowance and the remaining **65-second setup envelope** and rejects a return at
or beyond its deadline. No new setup interval starts at creation. Database and
worker creates, all other default controls and cleanup controls retain five seconds.
Their existing shorter explicit limits remain unchanged. The finite microfixture
supervisor and workflow files are untouched.

The 900-second workloads, 1,020-second supervisor, 55-second cleanup reservation,
55-minute Python job, fixed memory/CPU/swap/PID/tmpfs/network limits, cancellation,
uncertain-create handling, exact manifest ownership and both cleanup proofs are
unchanged. Existing bounded client reaping remains unchanged overhead, not
permission for more setup work. No assertions, skip identities, required restores,
collection completeness, retry policy or resource/qualification gate is relaxed.

## Finite local evidence

The expanded tests first failed **32** cases with **6** existing-cap controls
passing on the old code. The focused final selection passed **38**. The combined
supervisor, receipt and serial-shard suites passed **509**, zero skips, using the
frozen-lock Python3.13.5 environment. Independent source, test and documentation
review passed with the same 509 checks. Full collection is 4,727 cases (14 added);
required restore and expected-skip identities are unchanged.

Fourteen virtual-clock cases cover consumed setup of 0, 49, 50, 51, 64.5, 65 and
66 seconds, each with command timeout or return at the setup deadline. They prove
15-second selection, remaining-time clipping, no command once exhausted,
post-return rejection, conservative `creation_uncertain`, no workload launch and
unchanged owned reconciliation. Existing terminal-path vectors now explicitly
check canary/database/worker create limits of 15/5/5 and other controls at most
five seconds. These are finite control tests, not a hosted Docker latency result.

The single new normal hosted validation must bind the final published source. Preserve every failed result. If this candidate still
fails, stop for diagnosis; do not rerun unchanged source or widen another limit.
Physical devices, actual-volume recovery, capacity and installation acceptance
remain open under their separate gates.
