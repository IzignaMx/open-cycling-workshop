# S2b · First control-flow exception during quote cleanup

Assistant-selected bounded design under delegated architecture authority,
2026-10-29. Base `73661dbe86d54e19cad464f48e959cd001d202b7`, tree
`2c06102f24a42d6188a4d5e92e9f36d82698dc82`. Independent design review accepted the bounded policy with the clarifications
below before TDD. The coordinator selected this as an assistant-delegated choice,
not human semantic approval. The design decision alone does not establish execution qualification.

## Decision and source boundary

The first observed `BaseException` that is not an `Exception` wins over ordinary
command/cleanup failures. Preserve the identical earliest object and captured
original traceback chain as the final traceback suffix; a later cancellation
cannot replace an earlier cancellation, even if it re-raises the same object.
Raising adds propagation frames: preserve the origin, not a byte-identical whole
traceback chain. CancelledError, SystemExit and KeyboardInterrupt have no relative
priority. BaseExceptionGroup is classified as one object, without recursive
splitting or a new subgroup policy. No actual signal delivery or hard cancellation is implied.

At this base, `quotes/service.py` catches command failure before rollback or
invalidation (lines 345–356), catches every cleanup BaseException (377–390), then
releases the hook (357–370). Cleanup-origin control-flow exceptions are currently
lost. `_failure` already preserves command-origin control-flow exceptions.
The persistence/online-command ADR's atomic receipt, serialization-before-COMMIT,
same-ID/proof reconciliation and original deadline remain unchanged.

Reject original-error-always-wins because it loses cleanup cancellation; reject
last-error-wins/immediate rethrow because it replaces the first control-flow
exception or skips remaining owned cleanup. Reject wrappers, ExceptionGroups,
new exception fields, durable ledgers and a new executor as out of scope.

## Minimal private representation and ordering

Inside each `QuoteService.execute` invocation, keep one local
`tuple[BaseException, TracebackType | None] | None`, initially None, and a local
`capture_control_flow(error: BaseException) -> None` closure. Capture only when
the tuple is empty and the error is not an Exception; retain `error.__traceback__`
at that point. No instance/global/session storage or reusable framework. A propagated traceback
necessarily retains stack frames/locals while the caller keeps it; no promise of
zero retained references. Do not add persistent roots or retain all secondary
exceptions.

Private helpers become `_rollback(self, capture: Callable[[BaseException], None])
-> bool` and `_invalidate(self, capture: Callable[[BaseException], None]) -> bool`.
Their booleans retain existing ordinary cleanup meaning. Call order:

1. Capture the original command exception before any cleanup. Retain existing
   driver/OSError invalidation versus other-error rollback selection and `_failure`
   mapping; pass the same capture closure through nested helper calls.
2. A rollback exception is captured before invalidation. Invalidation marks
   `ocwp_quote_unusable` before calling the driver; any exception there is captured
   before returning False. A rollback failure still returns False even if later
   invalidation succeeds. No retry, reconnect or extra cleanup attempt is added. The maximum topology
   remains one rollback, one primary-path invalidation plus a possible second
   invalidation after release failure, and one release attempt.
3. Always attempt the existing release path. Capture a release exception before
   invalidation; keep cleanup_unverified classification and quarantine behavior.
4. Complete existing cleanup bookkeeping. If a control-flow tuple exists, raise
   its identical object with the captured traceback using `from None`; otherwise
   retain existing failure/success behavior. No success after observed cancellation.

Quarantine interrupted cleanup before further recovery calls. Reject subsequent
business use of the same Session through its existing unusable guard. Successful
invalidation does not prove backend death or bounded elapsed time. Bounded call
count does not mean bounded synchronous duration. Do not attach notes/fields,
stringify, log, persist or expose raw exceptions or traceback contexts. Suppressed
exception display does not erase internal context or make it safe to serialize.

## Deterministic acceptance matrix

Use existing SQLite application-service fixtures and real synthetic-fixture
commits, injected exception objects and call-order spies. No actual process signals.

| Row | Injection                                                                | Required assertions                                                                    |
| --- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| 1   | Ordinary encoder error; rollback C1                                      | Same C1; no commit; quarantine; release attempted; no success                          |
| 2   | Driver error; invalidate C1                                              | Same C1; quarantine before invalidate; release attempted                               |
| 3   | Ordinary encoder error; rollback OSError; invalidate C1                  | Same C1 captured in nested helper; no retry                                            |
| 4   | Actual commit succeeds; release C1                                       | Same C1; quarantine; fresh same-ID/proof canonical receipt replay; one effect tuple    |
| 5   | Actual commit then synthetic ACK-loss OSError; invalidate C1             | Same C1; no rollback/no-effect claim; fresh exact receipt replay, no duplicate effects |
| 6   | Original C1; rollback/invalidate/release C2 variants                     | C1 identity and original traceback origin retained; quarantine; existing call ceiling  |
| 7   | Cleanup C1 then secondary C2: rollback→invalidate and release→invalidate | C1 wins; remaining bookkeeping runs; no success                                        |
| 8   | SystemExit/KeyboardInterrupt sentinel variants                           | Same first-non-Exception rule and captured origin; no actual signal                    |
| 9   | Existing ordinary-only and S2a regressions                               | Existing codes/unknown/cleanup flags and all four S2a tests unchanged                  |

Assert first-observed traceback chain identity as a suffix, including a marked
origin and a secondary raise of the same object; normal prepended propagation
frames are permitted. Assert no new persistent service/session roots after handling.
Where rollback is interrupted, remove the injected fault and finish fixture teardown
outside the asserted service lifetime; teardown is not service-cleanup evidence.
A still-open transaction must remain quarantined, not described as rolled back.
SQLite release-path tests do not prove removal of an installed PostgreSQL hook.
Canonical receipt content equality does not mean whole-response byte equality.

## Validation and boundaries

Add failing tests first for the lost cleanup exceptions and first/last dominance;
retain existing passing semantics rather than claiming every row is a new bug.
Use targeted capture-removal/dominance mutations if a passing row needs sensitivity
proof, restore production bytes, and rerun affected tests. Independently review
exception lifetime, call ordering, privacy and exact source before publication.

No change to ordinary QuoteServiceError fields, COMMIT-unknown handling, financial
writes, replay identity, command serialization, budgets, routes, grants, SDK,
workflow, dependencies or public errors. No hard CPU/DB cutoff, actual network
COMMIT loss, backend absence, capacity, physical acceptance or deployment claim.
Historical S1 local whole-suite failures remain unqualified; do not blindly repeat
that broken RLIMIT_AS harness. Hosted exact-source qualification remains separate.

## Local implementation checkpoint · 2026-10-29

Initial RED also exposed a test-fixture snapshot mistake: existing write-admission
Session.info metadata was initially omitted. Correcting the test, without changing
production, gave 10 failed / 4 passed new cases: lost cleanup control-flow and
same-object traceback mutation are genuine baseline failures. Two additional
variants cover the maximum cleanup topology and same-object nested invalidation;
all 16 new variants and all 25 existing application-service cases pass.

Five temporary mutations (omit invalidation/rollback/release capture, select last
instead of first, omit traceback restoration) each failed as expected; production
was restored. A first mypy run rejected reuse of an except-target local name at
final propagation; rename to `selected_error` resolved it without behavior change.
Final affected suite: 417 passed, zero skips, one existing Starlette warning;
collection 5,101. Mypy passes all 124 source files; Ruff, generated contracts and
repository checks pass. No whole-suite run under the known-broken local RLIMIT_AS
harness. Independent implementation review and fresh hosted qualification remain
pending; local evidence does not supersede historical failures or external gates.
