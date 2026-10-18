# Quote oracle static-format closure

Status: exact source packet independently reviewed; execution pending.

The [corrected functional run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082181517)
passed all 66 selected functional cases, six selection mocks, repository
verification and lint. Its formatter failed with a complete, untruncated
9,755-byte output. Preserve that failed result and its three unrun later
commands.

Apply only the 15 retained layout hunks in `quote_integrity_checks.py`,
`quote_integrity_postgres.py` and their selection mocks. Independent review
matched each hunk to the exact source and found no changed tuple structure,
condition, assignment or assertion meaning. Product code, frozen oracles and
functional test bodies remain unchanged.

Use the existing contained mechanism for one fixed `selection_static12`
workload: six existing mocks followed by repository, lint, formatter, strict
production types, OpenAPI and generated-client verification. Refresh exact
source pins and the literal branch/workflow scope. All consumed workflows stay
unchanged. The workload retains 20 seconds, one CPU and 512 MiB, with the same
bounded setup, cancellation canary, diagnostics and independent cleanup.

This packet does not include another functional or capacity run. Exact source
review is complete; runtime receipts remain required before recording a pass. A failure,
missing/truncated output or unrun tail remains failed; no automatic retry or
larger budget follows. The final clean integration candidate and complete CI
gate remain pending separately.
