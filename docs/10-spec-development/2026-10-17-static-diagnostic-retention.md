# Retain actionable standard Ruff diagnostics

## Actual diagnostic qualification and next correction

[Run 39049797128](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39049797128)
on commit `5513ead255ec64128de1230009dc7fe0bc4acba1`, tree
`aaa9578ccaabbc15e0526019b53d65f3b7f66c59`, passed repository verification
and failed Ruff. Artifact `12107027091` is 1,901 bytes, SHA-256
`893421506573b3c04442444a90020ce381f697a58934c69d2a0804e4a58ae8e7`.
The receipt retained all four reported diagnostics with zero omissions:

- `SIM905`: guard's fixed mypy-code collection built through `str.split`.
- Two `RUF043`: anchored error-message regex literals without explicit raw syntax.
- `SIM300`: the static wrapper's inverted path comparison.

One unparsed line means `complete=false`; its content is unknown. Format, mypy,
OpenAPI and generated-client checks were unrun. Cancellation, client reap and
both absence receipts are retained for independent verification. This run does
not qualify PostgreSQL or product activation.

The next source candidate corrects exactly these four observed findings without
changing rule-set values, regex meaning, command selection or execution limits.
It uses the existing fixed six-command qualification. Source review and actual
checks on that corrected candidate are pending. The preparation description
below records the diagnostic change already executed, not a new pending design.

## Observed failure

[Run 39048370590](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39048370590)
tested commit `038a463c3339210488a80e5c8b0d61fc83edfdad`, tree
`1e68b89488d65ba8f828da122e48ae9d34be51ba`, once. Repository verification
passed; Ruff exited 1. Format, mypy, OpenAPI and generated-client checks were
unrun. Artifact `12106453817` is 1,599 bytes with SHA-256
`acdcb779df5649862d17c14126b3b682e951c4cb83891ec922240acd594cf1c6`.

The wrapper observed 679 output bytes and seven unparsed lines. It retained no
rule or source location. Those counts do not establish the number or cause of
the remaining errors. The closed known-rule catalog and uppercase-only parser
can discard useful standard diagnostics. In particular, lowercase syntax codes
are unsupported; this observation does not establish a syntax error in this run.

Independent review confirmed source/run/archive identity, cancellation, client
reap and both absence receipts. The 3.456-second supervisor interval includes
2.193 seconds of setup and 0.105 seconds of cancellation. Resource samples are
last observations, not a final workload census. The earlier static and repair
failures remain preserved at their original commits and runs.

## Minimal correction under preparation

Keep the same six fixed commands and product source. Correct only the existing
Ruff diagnostic path: exact selected public-source paths, bounded line/column,
generic diagnostic codes and standard concise single-line messages. Do not
maintain a manually enumerated Ruff rule catalog. The fixed command requests no
source excerpts; configuration, source paths and cleared environment are reviewed
before publication. No credentials, private fixtures or application data enter
the lint invocation.

Use the existing marker and post-stop/reap spool read. A Ruff-only 12-KiB marker
budget fits inside the unchanged 16-KiB host spool with framing overhead. Retain
whole records by byte budget and state every omission or unrecognized line
explicitly. This is not a guarantee of lossless transport for every possible
16-KiB tool output. Other tools retain their current diagnostic contract.

The worker remains limited to 20 seconds, one CPU and 512 MiB, with the same
unused database overhead, cancellation and cleanup. No new exporter or diagnostic
process is introduced. Source review and focused tests are pending; no local
candidate execution is claimed. The existing static qualification is the next
finite verification after independent review, with first failure and unrun
commands reported faithfully. No speculative product repair accompanies it.

Genuine PostgreSQL-0012 semantics and schema-0013 reconciliation remain the next
functional priorities after static closure. No activation, capacity, deployment
or main-branch integration is qualified here.
