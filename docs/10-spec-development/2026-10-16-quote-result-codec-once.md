# Reconstructed operation result codec reuse

## Scope and evidence

Prepared separately from qualified PR55 product source: remote
`7c0dc84bf763cac7523f55f4fbc7d0a06c362b07`, local equivalent
`3946942ac91af47fdc9d492e319bb070386c7ec8`, tree
`5cd0717146d7f33331845ed08d1f95687e653df6`.
No consumed profiling workflow is inherited, edited, renamed or revived.

[PR56 diagnostic run 38948546832](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38948546832)
failed at the immutable 20-second workload deadline during the host DB pressure
probe. Four revision actions were complete; fresh load was active in the last
checkpoint and exact retry was unavailable. Worker and DB were verified stopped,
then absent; separate cleanup also passed. Artifact 12067237886 remains preserved.
The observed action walls were 1.709/2.635/3.689/4.934 seconds; locked load spans
0/1.000/1.944/3.004 seconds and candidate spans 0.161/0.307/0.474/0.615 seconds.
These are instrumented, overlapping observations, not an uninstrumented benchmark.
The gap between four completed action intervals and the last checkpoint cannot be
assigned entirely to bootstrap, profiling, unfinished load or host monitoring.

## Two discarded validations

During reconstruction, each generated revision head was passed to
`encode_quote(head)` and later to `_logical_record`, which calls the same encoder
on that same operation-time head. Decision entries likewise reached
`encode_entry(entry)` before the logical formatter repeated it. Each encoder
validates and roundtrips its input, including descendant domain validation.

Remove only the earlier discarded calls. The remaining nested head guard is
combined with the same short-circuit order to satisfy Ruff SIM102. The intervening receipt/association and
outbox checks read the same immutable head/entry and operate on local maps; no SQL
write occurs. The logical formatter remains mandatory for every operation and
retains both the encoder and joined-record bound. All public constructors, stored
row decoding, generated predecessor validation, proof/admission checks, per-quote
customer evidence timing, outbox equality, completeness/cursor checks, final public
ledger and `validate_storage_ledger` stay intact. No cache, trusted flag, public
signature change, serialization shortcut or candidate-advance change is introduced.

One codec call per stored revision/decision is eliminated. This is a structural
count reduction only. Final full-ledger validation, row/target filters, candidate
validation and canonical proof roundtrips still cost work. No duration, percentile,
32-revision feasibility or overall linearity follows.

## Compatibility and test gate

A malformed history may reach a different internal first check. Public rejection
must remain the same closed `QuoteIntegrityError` category/message, with no input
mutation, durable effect or partial returned object. The original operation-time
logical bytes, receipts, ledger and history byte count must be identical.

Freeze complete PR55 reconstruction and its local formatter dependencies as an
independent test oracle. Use only tiny histories with at most three revisions and
four lines, including mixed decisions/corrections/withdrawals, Unicode, lowered
exact/+1 limits and malformed prefixes. Compare per-ordinal identity/bytes, count
reductions, unchanged predecessor/final checks, input immutability, errors and
rollback. Monkeypatch contamination checks establish formatter independence.
Existing PR52 oracle coverage remains unchanged.

TDD first failed on redundant local codec counts (quote 5 versus 3, entry 2 versus 1)
after exact bytes/ledger/input checks already passed. After removal, all 15 new tiny
cases passed. The mixed two-revision/one-decision fixture retains one predecessor
codec and final storage codecs for two quotes/one entry. Existing selections also
passed: 26 single-pass differential cases, 25 repository cases, 14 byte-reuse cases
and 57 corruption cases; 82 PostgreSQL parameter cases were explicitly deselected.
Each invocation had a 20-second external limit; no full-shape specimen was selected.
This is 137 passing cases across separate runs, not one aggregate suite.

Ruff lint/format and mypy on the touched production module pass using existing
locked tools. The frozen PR55 oracle's SHA-256 is
`113eab84cdfb5fc33babb0427de0f31339e2a79bbb934da742ffddbf6b41521c`,
identical to the base reconstruction source; repository-wide REUSE annotations
cover both new test files. No dependency installation occurred.
Independent source/document review passed; the reviewer independently ran the
15 new cases after the guard combination (3.40 seconds). Exact package review and
ordinary hosted qualification remain pending. No further profile or maximum
execution is authorized by this patch; latency, contention, restored-history and
activation gates remain open.
