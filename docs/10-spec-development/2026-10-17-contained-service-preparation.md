# Contained service qualification preparation

2026-10-17. Local unexecuted preparation only. No workflow has been published or run. The existing maximum/profile experiments remain consumed and unchanged.

## Scope

The existing quote-capacity supervisor gains a fixed service-initial mode: six exact existing service/DTO cases in one 20-second process including import, collection, setup and teardown. Existing container ownership, limits, canary and cleanup are reused. Closed result parsing requires exact setup/call/teardown success, session finish and process exit; timeout/failure begins bounded container cancellation before client reaping or diagnostics. No arbitrary selectors, thresholds, matrices or retries are introduced.

The proposed quote-service-contained.yml workflow triggers immediately on its one fixed branch push, first run and first attempt only. Publishing that branch is therefore execution, not passive storage. Opening a PR additionally triggers ordinary CI. Neither action is authorized by this preparation document. A consumed/skipped first run stops; do not rename/increment/retry to obtain a launch.

## Prerequisites

1. Exact static review and a separately accepted finite guard-test invocation in an independently contained worker. The changed service supervisor cannot certify its own mocked tests as independent containment. The smallest proposed bootstrap uses frozen baseline containment helpers and one fixed invocation recipe; it is not implemented here. Do not build an endless guard-of-guard chain.
2. Verify actual source/image/control identity, descendant cancellation and successful absence; preserve failure evidence. A green badge or client exit alone is insufficient.
3. Reconcile and independently review the service candidate against the exact source tree before publishing the service-trigger branch. These three guard source files alone do not contain the selected service modules/tests.
4. Schema 0013 is separate. The frozen service writes populated effects without order_effect_version and must not be overlaid unchanged onto 0013: the new CHECK would reject it. Adapt all new writes to the explicit version contract; validate historical null receipts and reject unknown/missing versions on linked effects. Replay must preserve immutable identities and fresh authorization. No guessed version/backfill is allowed.
5. PostgreSQL 18 real schema/migration/restore and bounded-read evidence remain separate gates. SQLite functional tests cannot establish them or performance/activation readiness.

## Evidence status

Guard tests and service tests are prepared, not executed. No import, compile, collection, lint, formatting or container launch was performed for this package. The proposed 20-second ceiling is a qualification ceiling with bounded termination grace, not proof that a stalled Docker daemon can be stopped instantaneously. No API, service activation, account permission or deployment changes are included.
