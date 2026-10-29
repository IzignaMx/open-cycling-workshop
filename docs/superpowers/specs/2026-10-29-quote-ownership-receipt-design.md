# Ownership receipt uncertainty and pre-GO failure

Assistant-selected bounded correction on main `c2512681c8c2169dc5b39eaddd7ef4042b8c7064`.
Independent design review precedes implementation. Actual run40927223929 is spent:
protocol failure, no accepted H/S observation, actual admission unknown, both owned
cleanup receipts verified absent. This correction neither reruns that experiment nor
identifies its historical root cause. Historical artifacts remain immutable.

## Decision

A host that has not accepted a complete owner observation must not manufacture
`skipped`, false reservation flags or zero elapsed time as execution facts.
New receipts use schema2 and required `owner_observation`:

- `unavailable`: overall status failed, fixed failure code, setup_ns/elapsed_ns,
  observer and resources all null; cases exactly `{name: H, status: unknown}` and
  `{name: S, status: unknown}`. Cleanup remains separately evidenced. This says no
  observation was accepted, not that processes or SQL never ran.
- `accepted`: unchanged closed owner observation and resource validation, including
  all current success constraints, plus exact source/run/image identity. Failed
  owner observations retain their partial known facts. Passing or pending-cleanup
  receipts require accepted observation. Cleanup cannot upgrade unknown evidence.

Schema1 decoding remains available only for historical interpretation. Its fallback
skipped fields cannot prove non-admission. New host writer, finalizer/sealer and
artifact stager require schema2; schema1 must not qualify a fresh run by compatibility.
Unknown keys, enum values, noncanonical unavailable shapes and success/unavailable
combinations remain rejected. Receipt cap16384B and frame cap4096B stay fixed.

A second concrete integration defect masks an owner's valid failed teardown RESULT
when it arrives before RESERVED. First host frame may be only RESERVED/setup or a
fully validated RESULT/teardown. Early RESULT must be failed, elapsed_ns0, both
cases skipped with no starts (the existing closed validator enforces empty case
facts). Preserve any valid partial observer setup facts; do not require them false.
Never send GO after this terminal result. Keep exact identity/sender/sequence,
original setup deadline and owned-client reap checks. Reject observed-success RESULT,
nonzero elapsed, started cases, wrong identities, invalid ordering and other events.
No arbitrary exceptions, SQL, credentials or stderr are retained. Database refusal
classification remains separate; this change does not invent historical attribution.

## Alternatives rejected

Relabeling schema1 skipped silently rewrites historical meaning. Merely adding prose
leaves machine consumers exposed. Logging raw worker stderr breaches the closed
privacy boundary. Building a generalized event ledger or extra runtime probe expands
scope and is unnecessary for conservative unknown output.

## Proof and limits

Pure/mocked tests reproduce observe exceptions before/after synthetic GO and accepted
pre-GO failure frames. No actual child/DB/Docker execution. Legacy historical decoder
roundtrip remains; fresh staging/finalizer rejects legacy. Positive existing success
and negative malformed cases remain unchanged. Fixed workflow identity, consumed
run guard, resources, deadlines, routes, grants and production activation are untouched.

## Local verification checkpoint

Twenty-six new pure/mock regressions passed; all456 ownership and741 combined
ownership/retained containment tests passed serially under900s/768MiB. Initial RED
showed missing schema2/legacy rejection and masked pre-GO failure. An initial test
fixture attempted dummy FD setup and failed before the intended assertion; corrected
in-memory transport produced the expected protocol RED. Strict mypy3 source files,
Ruff5 touched Python files and locked Prettier4 documentation files passed.
Exact-patch independent review and new hosted/full-suite qualification remain pending.
No actual runtime, database, fixture or process-stop experiment was repeated.
