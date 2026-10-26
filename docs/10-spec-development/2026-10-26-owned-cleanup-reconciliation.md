# PR #58 · Owned cleanup and native negative matcher reconciliation

## Source-bound failed checkpoint

Status: **implemented_pending_evidence**; independent code review passed, while
final documentation review and hosted evidence remain pending. This bounded CI/test correction
follows AGENTS.md, Master Agent Loop v0.2, Foundation v0.2 and the Phase 10
evidence-before-status rule. It introduces no product architecture decision.

Preserve [CI 40249194704](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40249194704)
as **failed** for published head `41263b4012659c0baf3475b2a7a3e763fe2856e7`,
tested merge `873e7101b6a2ff38d877ae1b0a5e20dcd1fbcd25`, tree
`2877e3e8666397335e3c0255ddd0147c2b633a8a`, against base main
`8a7eeecc39b0a43097484d10dc30af541ae38156`. It is not a complete qualifying
successor to the earlier source-bound passes. The previous
[readiness correction](2026-10-26-branding-administration-readiness.md) and
[October 25 checkpoint](2026-10-25-pr58-status-reconciliation.md) remain historical.

Both the direct and aggregate native browser reports contain **84 passes,
two failures and zero flaky passes**. The two new negative readiness controls
fail at rejection matching; these reports must not be called clean browser
acceptance. The positive native readiness controls do not erase the failures.
The AST-extracted helper returns a Promise from a VM realm. The rejection
matcher rejects its foreign-realm Promise before matching the intended timeout.
The narrow correction normalizes it through `Promise.resolve(...)`, preserving
the underlying resolution/rejection, timeout expectation and final DOM absence
assertion. Resolved promises and wrong-error rejections must still fail.
No production helper, authority, grant or admission behavior changes here.

Full Python stopped **before collection**: the canary's Docker create command
hit its existing five-second command timeout. The receipt records
`creation_uncertain`, no collection or result, and failed primary cleanup.
Independent shard A cleanup also failed with an ownership manifest present;
shard B reported `no_ownership_manifest`. Neither receipt proves historical
owned-container absence. Builder cleanup remains **not assessed**. No Python
pass/skip/restore count may be inferred for this run.

The original Docker create timeout and failed cleanup root causes remain
**unknown**. Retained evidence lacks historical CID-file contents and a precise
cleanup exception. Local synthetic reproduction establishes a narrower weakness:
an empty, newline-only or partial hexadecimal CID hint was rejected before a
daemon ownership check. That is not proof this weakness caused the hosted event.
A later successful cleanup implementation cannot retroactively prove absence
on the old runner.

## Preserved evidence

These are artifacts of the failed checkpoint, not the pending candidate:

| Evidence           | Artifact ID | ZIP SHA-256                                                        |
| ------------------ | ----------- | ------------------------------------------------------------------ |
| Direct browser     | 12620745365 | `717fd6624a1548929faca9146ddbf9349f84c3cf8de0dd4d68e8cf3187271d24` |
| Aggregate browser  | 12621315061 | `4ed23d6f3213a94753b639e8e4365b3439c26a78dbf757a5683f0479dbf42fa1` |
| Aggregate verifier | 12621130856 | `4d44ae1fe519958c4d109b2a4dba2085941effbef7fa69c24121369aab4b1152` |
| Failed Python      | 12620187257 | `2abc032c5d358950d350cb0a0cf6b457c4d228c159966314defa1a68cc9d7366` |

Artifact links use the preserved [run's artifacts](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40249194704).
Same-head Security 40249194693, DCO 40249194690, containment 40249194674 and
Local runtime 40249194731 passed. Runtime retained eleven checks, three restarts,
restore, native ARM64 decoder and three image builds. These separate successes
do not resolve the failed Python cleanup or establish physical-device evidence.
Optional QEMU 40249194688 failed, **NON-QUALIFYING**: original child parent-wall
timeout; the separate diagnostic child last reached `decode_start`. The original
cause remains unproven. These results are not inherited by the new candidate.

## Approved bounded successor and acceptance

The user's October 26 17:54 approval covers strict manifest-owned handling of
incomplete CID hints, bounded cleanup diagnostics, the negative matcher correction
and **one fresh complete normal validation**. It does not authorize retries,
extra consumed experiments, a budget increase, merge, deployment or real-data
mutation. Publication and normal validation remain the parent task's controlled
steps after final local evidence and independent review, not an instruction to
manually dispatch duplicate workflows.

The cleanup correction must treat incomplete CID content only as an untrusted
hint. Exact manifest ownership and live identity checks remain authoritative;
no broad name/prefix deletion, unrelated resource cleanup, ambiguous-identity
acceptance or absence claim from an inspection error is allowed. Only empty/whitespace-only content or a strict lowercase-hexadecimal prefix can
be treated as an incomplete hint; a valid manifest and exact live image, name
and owner-token checks remain necessary. Missing/malformed manifests, malformed
CID strings, foreign full IDs, daemon errors and surviving containers still
refuse qualification. Valid full CID mismatches must still fail closed.
`creation_uncertain` remains a workload failure even if subsequent cleanup proves
absence. Both primary and independent cleanup must
prove final absence before qualification; diagnostic sidecars are bounded,
redacted and explicitly **non-qualifying**, never substitutes for receipts.

Retain the existing five-second create command boundary, two serial 900-second
Python workloads, 768-MiB worker, 1,024-MiB PostgreSQL memory, 512-MiB database
data mount, one CPU each, zero swap, and 55-minute exterior job. No timeout,
retry, workload/cleanup budget, dependency, assertion, large fixture, intentional
skip or mandatory restore requirement is relaxed.

The workflow change adds only four explicit artifact upload paths: `primary-cleanup-diagnostic.json` and
`independent-cleanup-diagnostic.json` sidecars for shards A and B. No command,
timeout, resource limit or broader artifact glob is added. Its regression first
failed once with the missing upload paths and then passed all seven focused
checks after the correction.

Local verification of the current matcher/frontend scope reports four real-runner
matcher controls passing after a three-failure/one-pass RED run; resolved and
wrong-error rejection refusal remain enforced. All 934 frontend core tests,
normal and focused TypeScript, lint/format and production PWA build passed.
These ran on Node 24.22.1, whereas normal CI pins 22.16.0; hosted compatibility
is still pending. The PWA build retains its existing large-chunk warning.
These are local scoped observations, not final-tree or hosted qualification.

Independent code review passed. All **271 cleanup-helper cases** passed,
including 43 added regressions; the unchanged receipt/verifier subset also
passed 136 cases. The final combined helper, CI-contract, verifier and serial-shard
selection passed **502 tests with zero skips**, independently repeated by the
parent. These are overlapping selections, not additive test totals. Ruff and
diff whitespace checks passed. Synthetic regressions against the original source
retained 43 failures with 16 passing controls; no local Docker execution or
historical runner absence is claimed. Final documentation consistency review
and exact-successor hosted results remain **pending**. Require exact-source complete collection, exact intentional
skip identities, all six mandatory restores, both shard containment/primary and
independent absence proofs, native direct and aggregate clean browser reports,
existing retry-free repetitions and all companion workflows. Preserve failures;
a green exit or diagnostic sidecar alone is insufficient. Record terminal
results in PR metadata without inventing a self-referential commit hash.

## Gates not closed by this increment

V0.1 remains partial and PR #58 draft/unmerged. Preserve AGPL-3.0-only, DCO,
Offline First/Local First, security, accessibility and data integrity. Shared
branding FR-WL-001/002 and explicit independent grants remain unchanged.

Actual Windows/Android Tier 1 acceptance (R01-T035), assistive technology,
laptop/Raspberry hardware, installation inventory and isolated restore/corruption
with measured RPO/RTO remain open. Hosted native ARM is not physical Raspberry
qualification. Full-history pre-reopen validation required by the
[bounded-effects amendment](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md)
and semantic closure is still separate work. Keep quote API/UI closed, remaining
ingress/enrollment/authority/grant-adoption/old-writer gates open, and capacity,
latency and contention unqualified. Preserve real journals, volumes, assets and
TLS identity under the [runtime runbook](../07-operations/2026-10-14-local-runtime.md).
