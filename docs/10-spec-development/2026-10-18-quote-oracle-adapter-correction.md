# Quote-only oracle adapter correction

Status: all 66 functional cases passed; the combined static group failed
formatting after its mocks, repository and lint checks passed.

## Recorded corrected-source result

[Run 39082181517](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39082181517)
executed once on commit `b353c4b4d364ebfbcd1dc98134017c8bc6aae609`, tree
`7136fdb0d7d5642839af9963caa09461571d8775`, attempt 1/1.
Its four artifacts and primary/independent cleanup receipts were reviewed.
The three functional groups passed 26, 15 and 25 cases respectively. The final
group passed six mocks, repository verification and Ruff, then retained the
complete 9,755-byte formatter output: 15 layout hunks in three auxiliary files,
with 46 other files already formatted. Typing and both contracts were unrun.
The 78-check selection therefore records 74 passes, one failure and three unrun
checks. It remains a failed workflow, with the original failures preserved.

The observed argument-binding failures are resolved on this source. The next
correction applies only that retained formatting diff and qualifies the
mock/static group separately; it does not rerun these 66 functional cases.

## Observed failures and minimal correction

[The existing regression run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39080692255)
failed three groups when historical test callables received the current
reconstruction keywords. Complete diagnostics establish argument-binding
`TypeError` before the intended assertions. This identifies test adapters;
it does not establish a product reconstruction failure or successful unrun cases.

Bridge only the two repository monkeypatches to their frozen quote-only oracles.
The explicit adapter accepts the current effect/checkpoint arguments, rejects
any linked-source rows and all five non-null effect fields, then invokes the
unchanged seven-positional oracle. It preserves its return value and exceptions.
Boundary checkpoints do not prove internal deadline equivalence. Direct oracle
comparisons and both frozen implementations remain unchanged.

The error-normalization double accepts the explicit current seam and raises its
retained synthetic exception. The assertion additionally requires that exact
exception object as the cause, preventing the TypeError parameter from passing
because of an unrelated argument-binding error.

The same run's final group passed six mocks and the repository contract, then
reported three SIM300 comparison-order findings in the selection mocks. Reverse
only those comparisons without changing their predicates. Add the affected
history-byte test module explicitly to the fixed lint/format scope.

## Corrected-source qualification

The following fixed selection records the historical preparation plan for that
executed run. Its resource limits remain applicable to the recorded evidence.

Prepare one distinct fixed selection using the existing contained mechanism:

- `sqlite_single_pass26`: 26 existing cases
- `sqlite_codec15`: 15 existing cases
- `sqlite_bytes_reads25`: 25 existing cases
- `selection_static12`: six existing mocks and six static commands

These 78 checks use four serialized workloads with independent 20-second
deadlines, one CPU and 512 MiB per worker. Their total business allocation is
80 seconds, with no borrowing or increased limits. Preparation, canary and
cleanup remain separate bounded phases. The original 23-group run, workflow
and evidence remain preserved.

Exact source pins, explicit new branch/workflow scope, complete bounded reports
and unchanged cancellation/cleanup passed independent source review. The result
above records its actual partial qualification. A new failure remains failed
and must be diagnosed before another action.

Product code, schema and command activation are unchanged. The final clean
integration tree and full-suite containment gate remain separate obligations.
