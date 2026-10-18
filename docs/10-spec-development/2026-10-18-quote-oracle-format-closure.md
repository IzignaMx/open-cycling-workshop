# Quote oracle static-format closure

Status: verified for the fixed 12-check scope; final integration remains pending.

The [corrected functional run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082181517)
passed all 66 selected functional cases, six selection mocks, repository
verification and lint. Its formatter failed with a complete, untruncated
9,755-byte output. Preserve that failed result and its three unrun later
commands.

## Historical preparation for run 39082876503

The following preparation describes that consumed qualification packet.

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

This packet does not include another functional or capacity run. The final clean integration candidate and complete CI gate remain pending separately.

## Verified execution

[Run 39082876503](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082876503)
completed its sole attempt with all 12 checks passed and zero failures, errors,
skips or unrun checks. Source commit `1d32c9a4b91b6e3b2cc0a1ec2c6e54329b24a5ef`
has tree `ef961b9a12780a3a618f3fe5bbcdd90bfce2cb9e`. Independent evidence review
verified 46 source pins, four locked inputs, image identity, the cancellation
canary, bounded stop/reap and primary plus independent resource absence.

The workload took 14.579792505 seconds under its unchanged 20-second limit;
final pre-termination worker peak memory was 283,918,336 bytes. Artifact
`12119921296` has SHA-256
`159ca7f4eab38fe64cbf5f76dad263150a4a2af91bc845912048d7355c13b475`.
This closes the retained formatter failure and previously unrun type/OpenAPI/
generated-client commands on this exact source. The prior failed run remains
failed. The separate 66-case functional result is not another execution here.
No full-suite, capacity, activation or installation qualification is inferred.
