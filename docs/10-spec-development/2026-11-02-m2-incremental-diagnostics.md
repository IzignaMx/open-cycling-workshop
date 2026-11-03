# M2 incremental diagnostics: local implementation, runtime unqualified

## Verified baseline and retained failures

PR83 remains a draft, not merged. Published head
`280c8923d773fea7eff420e1bbe26edcd22d4195` has tree
`1476ce82f8afa2ec11a3d70e5fdcf7da2f395384`, identical to local
`812eff4e3ece4962a773bb2c2da81a3a65f2eb3d`. Main remains
`e9c11ad11a564c80add99f4dc901ffe2d583c8e6`.

| Attempt     | Laboratory outcome                                | Cleanup evidence                                            |
| ----------- | ------------------------------------------------- | ----------------------------------------------------------- |
| 41518365154 | Image preparation failed; runtime skipped         | Unproven                                                    |
| 41527723967 | Preparation passed; runtime failed, cause UNKNOWN | Unproven                                                    |
| 41541751810 | Runtime failed, cause UNKNOWN                     | Owned containers absent and root removed, this attempt only |

The third artifact is 589 bytes, SHA256
`7f88ebc84d05f4835ebcb12272ae7a5d4568887f28cdd82509538193e53d70e2`.
Its two closed receipts match tested merge
`d5b4d14c3f44af3f92f316fc64cbd029755809f3`, the expected base/head parents
and reviewed tree. Cleanup is not secure erasure, nor retrospective evidence
for earlier failed attempts. No PostgreSQL/TLS/process acceptance follows.

Ordinary CI41541751816 separately passed 27/27 controls, 5851 Python tests plus
58 exact intentional skips, 1237 frontend tests and one API-client check.
Terminal logs report 126 direct browser passes; aggregate JSON reports 126.
Small reports prove repeats20/9/5/10 and kernel14 with one passing result each,
zero retries. Their bytes, hashes and source seals were independently checked.
The two approximately332MB browser ZIPs were **not** downloaded or byte/trace/
screenshot verified. Runtime41541751982, security41541752097,
micro41541752380 and DCO41541751844 also passed. These are ordinary CI evidence,
not acceptance of the failed M2 laboratory or this new diagnostic candidate.

Terminal receipts and the reviewed proposal are retained in Library version13,
`libfile_5d18c5ba18e481918e98ff90a96b8a66`, archive SHA256
`49c2e2b687131661acea0080c6b17aad3e5858b92b148f86bb8bfe6868455a2a`.
Historical preparation records remain snapshots, not current execution status.

## Missing evidence and bounded response

The supervisor's all-or-nothing assignment records checks only after full
success. The API similarly returns its check dictionary only after all probes
finish. Intermediate status was ephemeral and removed by verified cleanup;
container logging was intentionally disabled. Existing receipts do not locate
the failure. Duration and empty checks cannot establish which operation failed.
Bounded independent source review found no reproducible cause attributable to
the third attempt. Another speculative rerun is not justified.

The local-only increment adds closed, versioned diagnostic stages and completed
milestones, not raw logs or a new inspection interface:

- Supervisor progress records the first uncompleted/current boundary separately
  from completed boundaries. That label alone does not prove entry or failure
  within the operation. Partial milestones never satisfy the final success gate.
- API progress uses its existing status file and fixed check names. A validated
  snapshot remains explicitly API self-report, not independent OS proof.
- Source/tree/nonce, schema, file identity and bounded content are checked before
  projecting a snapshot. Unknown, torn, missing or invalid input becomes a fixed
  unavailable/refusal category; raw input is never copied to evidence.
- Snapshot work reserves time inside the existing760-second runtime budget.
  No retries, additional container inspection, timeout extension or new mounts.
- Diagnostic write/snapshot failures cannot skip independent cleanup. Hard
  termination may still leave missing evidence; no complete-crash guarantee.
- Keep exactly two JSON artifacts, combined at most 1 MiB and retained one day.
  Ordinary CI's much larger browser artifacts are a separate allowance.

No SQL, HTTP headers/bodies, exceptions, DSNs, environment values, private paths,
credential/CA/key material or catalogue values may enter diagnostic output.
Credentials retain the existing synthetic-only15-minute policy; no new access,
normal application route, human grant, production behavior or deployment.

## Local acceptance and consent boundary

Required tests cover failure at each boundary, retained completed milestones,
partial-never-passed outcomes, closed canary-free output, identity/schema/file
tampering, bounded snapshot failures and unconditional cleanup. Fake executors
and public fixtures do not qualify real PostgreSQL, TLS or container isolation.
Local verification: 5341 Python tests passed, 671 environment-dependent tests
skipped, with 12 warnings; 1237 frontend tests passed. Scoped strict type checking
passed for eight prepared sources, with Ruff and formatting checks for changed
Python files. Independent security/contract tests passed381 cases; a separate
functional review passed38 isolated API cases and124 controller/operation cases.
All16 supervisor boundaries have actual fake-operation fault regressions, not
only stage bookkeeping tests. Same-descriptor file-mode validation and valid
producer-to-consumer partial check prefixes close review findings. These are
local-source acceptance results, not a fix for the UNKNOWN hosted root cause.

Only local implementation and validation are in scope. All three hosted permits
are consumed: **no fourth attempt**, further publication or merge is authorized.
Any such action requires a new explicit decision on the exact reviewed package
and execution bounds. R09-T020/R10-T014 remain partial prerequisites, not full
M2/SDK completion. T1–T8/R01-T035 remain pending, ownership40927223929 is SPENT,
cleanup41011497919 remains historical UNKNOWN, and Pages is unchanged.
