# Quote operation replay without repeated prefix ledgers

## Scope

The parent approved bounded TDD of the independently reviewed reconstruction
redesign after PR52 ordinary CI closure. This slice changes only reconstruction
and its private serialization helpers; incoming repository candidate `advance`,
writer admission, locks, SQL queries, savepoints, caller commit, public snapshots
and domain constructors remain unchanged. There is no persistent cache, trusted
flag, forged dataclass, workflow change or new maximum execution.

The chronological operation loop keeps a normally validated current quote,
finalized predecessors and decision entries. Create uses `Quote.for_order`; revise
uses `head.revise` and exact stored predecessor/current-head comparisons. Decision
uses existing `_admit`, arithmetic and entry constructors. Every receipt and outbox
is checked at its actual operation position. Historical result bytes use that
operation's unsuperseded head, never the final head's representation.

The final public `QuoteDecisionLedger` is constructed, and unchanged
`validate_storage_ledger` runs once afterward. This deliberately validates the final
ledger twice. Instrumented mixed-history reconstruction observes three history
constructors and two ledger constructors total, independent of prefix count;
no complete prefix ledger is constructed in the operation loop. Individual changed
head/predecessor/entry codecs remain, preserving intermediate storage limits.

This removes repeated prefix-ledger validation, not all nonlinear work. Stored
revision reconstruction still filters row collections by revision and edges by
source line. Those residual scans are unchanged. No whole-reconstruction linearity,
maximum-capacity fit or latency improvement is claimed.

## Decisions and failures

Latest entry and latest non-null customer-evidence timestamp are per quote.
Every evidence entry replaces that timestamp, including a record correction to an
earlier time; withdrawal preserves it. Decision sequence and recording monotonicity
are global. Final validation rechecks active intervals and all decision relationships.

All five preexisting exception categories still normalize to the same public
`QuoteIntegrityError("stored quote history is invalid")`. For inputs with multiple
corruptions, the first internal cause can differ; no changed public category,
message, returned structure or raw error disclosure is accepted. No partial snapshot
or byte summary escapes on failure.

## Explicit invariant map

| Invariant                                                               | Existing enforcing code                          | Required one-pass preservation                                                                                                              |
| ----------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Root, bounded revisions/decisions, operation/outbox cardinality         | reconstruction initial guards                    | Same guards before any replay; monotonically increasing consumed counts cannot temporarily exceed final counts                              |
| Exact typed IDs, integers, UTF-8, depth, shapes                         | command/storage decoders                         | Same decoders on every proof and stored record; no Python equality shortcut for bool/int                                                    |
| Tenant/order/location/lineage scope                                     | advance, `_scope`, reconstruction associations   | Explicit root/current-head scope on each create/revise/decision, plus unchanged persisted-row scopes                                        |
| Authority/admission                                                     | repository `_admitted`, order/lineage locks      | Entire repository boundary unchanged; reconstruction never grants user authority                                                            |
| Financial amounts and line/edge limits                                  | Quote constructors, pricing, storage codecs      | Ordinary Quote.for_order/head.revise and price_selection; encode changed records; decoded stored records compared exactly                   |
| History contiguous versions, IDs, links, retained/retired lines         | QuoteHistory constructor                         | One normal stored_history validation plus per-step expected head/sequence and consumed IDs; compare generated pair with exact decoded rows  |
| Prefix head unsuperseded                                                | advance's live head                              | Keep unsuperseded generated head; validate final predecessor at next revise; never use a future-superseded quote as the current prefix head |
| Revision after latest decision time                                     | QuoteDecisionLedger.revise                       | Explicit comparison with last decision recording time before head.revise                                                                    |
| Decision initial/correction/customer_change/withdrawal                  | `_admit`, ledger constructor                     | Same `_admit` per entry with per-head latest/customer-time state; final normal ledger validation                                            |
| Current revision only, expected sequence, no duplicated decision replay | record and advance                               | Explicit current head/version/sequence check; identity consumed once; no replay-return branch inside reconstruction                         |
| Entry recording monotonicity and observed head progression              | ledger constructor                               | Check each newly appended entry against prior decision state, then final constructor                                                        |
| Decision amounts, selected/declined lines, evidence                     | price_selection, `_line_decisions`, decode_entry | Generate expected entry with existing pure helpers; canonical decode persisted entry and compare; no acceptance based on totals alone       |
| Every historical proof/result even if later superseded                  | old advance + logical_record each prefix         | Same operation-time head/entry and per-step joined record; compare each step before moving on                                               |
| Receipt order/identity/version/kind/actor/time                          | reconstruction operation loop                    | Same checks in supplied order, same consumption; no sort/dedup repair                                                                       |
| Outbox exact content and privacy                                        | event_payload canonical comparison               | Same formatting via shared private formatter and same per-step checked inputs; retain canonical comparison                                  |
| 256KiB record and16MiB history limits                                   | `_record`, storage validation                    | Validate operation-time joined records and changed quote/entry encodings; final array framing/depth validation unchanged                    |
| Partial data, cursor and orphan detection                               | end checks/map exhaustion                        | Same final checks, no partial snapshot/count returned                                                                                       |
| Errors                                                                  | private reconstruction wrapper                   | Same five error categories normalized to QuoteIntegrityError("stored quote history is invalid"); no raw exception/SQL exposure              |
| Replay and atomicity                                                    | apply full load before receipt lookup; savepoint | Same locked load and prior-proof check; unchanged candidate advance/savepoint/caller commit; failure creates no durable effect              |

## Independent tiny oracle and evidence

The test-only `quote_reconstruction_pr52_oracle.py` is a byte-for-byte frozen copy
of PR52 reconstruction, including its old `advance`, event and logical formatters.
Source commit: `476efcb19db7ab85a811fac250b1a6a819f0d99c`; SHA-256:
`a5763d863f20747d3c3651e764cfa9769e84d86872fa31dfa2a42c5692856280`.
Its domain, command and storage dependencies are unchanged by this slice.
Bidirectional monkeypatch contamination tests establish that old/new formatters
and replay paths do not silently share the new helper implementation.

The original corruption suite now runs each case independently through both
implementations. Additional tests compare complete ledgers, ordered receipts,
per-ordinal canonical logical-record bytes and full-history bytes. Fixtures use
at most three four-line revisions or separately small correction/withdrawal cases.
They include mixed corrections, withdrawal, later revision/new initial decision,
coherent reordered operations reaching current-head rejection, prefix preconditions,
customer-time replacement, UTF-8, exact/+1 record/history boundaries, and caller
rollback against both paths. No maximum shape/history is executed locally.

TDD first showed three old prefix `advance` calls where zero were required
(one failure, seven passes); the corrected loop passed that test. Per-operation
instrumentation verifies proof, event, logical result and actual outbox comparison
calls; per-decision `_admit` and final validations remain exercised.

The identical three-operation/four-line SQLite diagnostic changes storage-bound
`encode_quote` counts from PR52's 1/3/6 to 1/3/5 and full-storage-ledger validation
calls from 1/2/3 to 1/2/2. Apply-bound advance remains 1/1/1; reconstruction-bound
advance becomes 0/0/0. SELECT counts remain 6/12/12. These wrapper counts exclude
other imported encode aliases. Canonical-byte calls increase 112/209/317 to
112/221/341 at these tiny prefixes because conservative final validation adds
fixed work. No elapsed-time speedup is inferred from these observations.

## Remaining acceptance

The failed PR51 one-shot run 38900041213 and its twelve acknowledged revisions,
active thirteenth operation, partial counters and verified stop/removal remain
preserved. PR52 ordinary CI success qualifies its exact source, not this changed
tree or maximum capacity. Current candidate requires independent source/package
review and ordinary hosted CI. Any future maximum/profile verification requires
separate approval under unchanged or smaller containment budgets. The consumed
PR51 workflow is untouched. Ordinary API percentiles, organization-lock contention,
restore, physical devices and production activation remain open.

## Local verification closure

Three separately bounded small groups completed with exit 0: 26 new tests (6.11s),
57 differential reconstruction cases (11.49s; 57 PostgreSQL parameters explicitly
deselected), and 38 repository/byte cases (5.17s; 26 deselected: 24 PostgreSQL
parameters and the existing 100-line case in both dialects). Total 121 passes;
these are SQLite/pure checks, not hosted PostgreSQL qualification. An earlier
combined bounded invocation produced partial output without a terminal summary
and is not counted as a pass; the complete selected scope was then verified in
these small groups without increasing individual test-process deadlines.

Scoped Ruff, strict mypy for the changed production module, formatting and diff
checks pass. Reused tools: Python 3.13.5, pytest 9.1.1, Ruff 0.16.5, mypy 1.20.2.
No dependency was installed. The frozen oracle remains byte-identical to its
reviewed source and is covered by the existing REUSE.toml services/** aggregate
AGPL-3.0-only annotation. The local REUSE executable is unavailable; hosted REUSE
lint remains pending rather than being reported as executed.

Independent production-source and tiny-test review found no blocking invariant
gap. Exact final package/document review and publication remain separate gates.
