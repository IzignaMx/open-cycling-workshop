# Quote locked-history byte reuse

## Evidence and scope

The one-shot [PR51 trial](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38900041213)
failed with `command_timeout`: twelve revisions acknowledged, ordinal thirteen
active, no completed 32+1 profile. Setup took 1.985 seconds and total supervision
82.345 seconds. Aggregate exhaustion is strongly supported by those timestamps,
but the generic error does not identify the exact command/deadline. Both known
containers were verified stopped and then absent. Last resource samples are
partial, not final resource qualification. Preserve artifact 12045313271, ZIP
SHA-256 `cd6226e6427590f34a48265621b302057b949c3fa387b1f166f456f614d57654`.

The separate [ordinary tiny/fixed run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38900040965)
passed against that same tree. Its fixed joined records remain 207,781 and 66,065
bytes, or 273,849 bytes including array framing. It does not qualify longer
histories. No new maximum trial or changed execution limits are authorized here.

## Narrow implementation

Full locked reconstruction already validates every stored operation, financial
record, proof, association, cursor and outbox, and serializes the joined logical
records to enforce the complete-history byte limit. Previously `apply` replayed
all receipts a second time solely to recreate those byte-budget records.

A private reconstruction tuple now returns the same public snapshot plus that
validated canonical array byte count. Public `QuoteSnapshot`, `reconstruct`,
`load`, and `validate_history_bytes` contracts remain unchanged. Both private and
public reconstruction retain the existing normalized integrity errors. The count
is returned only after the final completeness/cursor checks. It is neither
persisted nor accepted from callers; `apply` obtains it from its current locked
load, preserving all queries, admission and candidate validation.

For an existing nonempty history, the candidate adds its canonical record length
and one comma. The candidate is serialized inside a one-record array (minus its
two framing bytes), preserving the original JSON depth validation. A new history starts with two bracket bytes. Every reconstructed
lineage necessarily contains at least one revision and its operation; an empty
stored lineage still fails. The same complete-history limit and error are checked
before the operation savepoint. Record limits and transaction ownership remain.

## Tiny verification

Test-first: three missing-count helper failures and one duplicate-advance failure
preceded implementation (four failures, two passes). Exact-byte tests cover empty
and nonempty arrays, UTF-8/escaping, exact and one-byte-over boundaries, operation-
time revision records, actual Unicode command content, initial decisions,
correction/withdrawal evidence, exact retries, unchanged snapshot fields, all five
normalized exception categories and rollback after byte rejection.

The identical three-operation/four-line SQLite diagnostic has apply-bound
`advance` counts 1/2/3 before and 1/1/1 after. Reconstruction remains 0/1/2;
combined calls are 1/3/5 before and 1/2/3 after. Storage-bound `encode_quote`
counts change 1/4/9 to 1/3/6. SELECT counts remain 6/12/12. These are call-count
observations, not PostgreSQL latency measurements or an 80-second fit prediction.
Nested validated-prefix work still grows quadratically per append. Public API,
ordinary-latency, contention, full capacity/restore and physical-device gates
remain open. No persistent cache, domain-validation bypass, new workflow or
production activation is introduced.

Selected local regression: 95 passed, 81 explicit unavailable-PostgreSQL skips,
2 deselected (the existing 100-line repository case, both dialect parameters).
The 14 new tests and existing small repository/reconstruction suites include
forged proofs, missing/duplicate rows, altered outbox/cursor/results, admission,
late-write rollback and historical retries. Scoped Ruff, strict mypy for the three
production modules, formatting and whitespace checks pass. Reused tooling is
Python 3.13.5, pytest 9.1.1, Ruff 0.16.5 and mypy 1.20.2; no dependency install.
Hosted PostgreSQL qualification of this changed source remains pending.

Independent review identified the candidate array-depth requirement. A tiny
12-level synthetic record regression failed before the one-record-array correction
and passes afterward; no production depth or size limit was relaxed.
