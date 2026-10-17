# Direct source repair after bounded static findings

## Evidence and scope

Prepared 2026-10-17; the manual changes and new qualification are not yet run.
The source base is commit `dff067af840b8e83d87d17ae6fa36cfd10e75653`, tree
`c3ba32738c5996badcf575bc47dfac9b9499fb4f`.

[Static run 39044828140](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39044828140)
passed the repository check and failed Ruff lint. Its closed receipt retained
12 source/line/rule records, omitted 134 other recognized unique records and
counted seven unparsed lines. This is not a complete total of all findings.
Format, mypy, OpenAPI and generated-client checks were unrun. Artifact
`12105845250` has SHA-256
`e28e452674aae3aea6ef20be6f014d144cdb625d94e39cf5292b4e92ec7a3c09`.
Cancellation, client reap and both absence receipts were verified; resource
figures were last samples, not final workload totals.

[Repair-proposal run 39046578616](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39046578616)
completed its first five phases and failed the sixth export/validation call.
No proposed patch or tool-status receipt was retained. The initiating export
exception is unknown; a compression limit is only one possible explanation.
Artifact `12106196731` has SHA-256
`07ff4744b0085fefaaadd45d0a07c3fa539836e473a62c006f28b2c63f441ef9`.
Cancellation, client reap and both absence receipts were verified. No generated
repair was applied and no source is inferred from the discarded private copies.

## Selected correction

Use direct reviewed source edits for definite style/import findings in the same
19 Python paths. Preserve product behavior, strict rules, configuration, locked
dependencies, schema 0012 and all previous workflow files. No unsafe fixes,
blanket suppressions, new exporter or wider output budget are introduced.
The separate repair-controller branch is not incorporated into this candidate.

Only the existing fixed static qualification mechanism is reused: repository
contract, Ruff check, Ruff format --check, strict mypy on six production roots,
mounted OpenAPI freshness and generated-client freshness. All six must pass;
maxfail=1 leaves later commands unrun after a failure. The source review and
actual contained result, not manual inspection, decide whether findings remain.

The new fixed workflow accepts only push to
`codex/quote-service-static-manual-qualification`, run 1/attempt 1. It preserves
the existing archived inputs, 20-second workload, one-CPU/512-MiB worker,
separate one-CPU/768-MiB unused database, output bounds, cancellation and
independent cleanup. No consumed workflow is retried. No local import, lint,
formatter, typecheck, compilation, collection or test is claimed.

After exact diff review and actual static evidence, prioritize the separately
reviewed small PostgreSQL-0012 service selection. Schema 0013 still requires
versioned-receipt and bounded-payload integration; neither it nor API activation,
capacity, installation or deployment is qualified by these static checks.
