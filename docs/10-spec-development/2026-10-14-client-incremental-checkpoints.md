# Increment C · bounded ongoing checkpoint client evidence

Date: 2026-10-14. Status: component implementation and local unit/static evidence;
production union, independent review, native browser and real server qualification
remain separate gates in the authenticated-workshop-client contract.

## Source and scope

Base: actual integrated main37 `14f4bf005f2b28ded5d31c45c9c532d50597aefc`, with
accepted C contract commit `c28dd08`. Component source commits:

- `f602924`: dependency-free bounded HTTP reader; initial baseline compatibility
  wrapper and streamed 16 KiB `/auth/context` boundary.
- `3217884`: separate null-baseline incremental parser, anchored bounded metadata,
  immutable initial completion proof and atomic projection/receipt/successor store.
- `53b9469`: immutable captured transport and one-page coordinator with bounded
  retry policy and visible permanent holds.
- `e29e14c`: final transaction lease/clock recheck, page-internal equal-version
  contradictions even below newer cached versions, and closed status-paired errors.

No kernel facade or shared type ownership changes are included in this component;
those are integrated separately. No schema migration, server route, publication,
deployment, actual account or installation change was performed.

## Durable invariants

The original baseline start and completed delta receipt remain unchanged. The
incremental format carries its original checkpoint, context/incarnation/owner,
safe local sequence, exact pending body and only the latest canonical receipt
with its exact predecessor body. The partition cursor always equals that latest
accepted continuation and next request, including `catching_up`. Completion of
that round is claimed only by its matching `complete` receipt. Local sequence and
anchor validate local atomic-transition metadata; they are not cryptographic
proof and cannot reconstruct discarded pages.

A valid complete initial set remains usable with valid partial incremental
progress within its session lease. Initial activation is never revalidated after
deltas. New private baselines explicitly drop inherited incremental metadata and
preserve the old partition and all journal/delivery/event history.

Projection merge, receipt and successor share one transaction. Scope, grants,
versions, exact latest replay, owner, generation, session-current callback and
lease/clock boundaries fail closed. Quota/abort/stale response leaves the old
rows and cursor intact. Lost response retries the exact durable body. Exhaustion
and permanent refusal hold visibly; failure to persist a hold disables the
matching volatile session. There is no zero/numeric cursor fallback or implicit
journal acknowledgment.

## Observed RED / GREEN

- Oversized context body was accepted before reader extraction; its new test
  failed with “Missing expected rejection,” then passed with streamed cancellation.
- Incremental wire/store/transport/coordinator tests first failed on absent modules.
- Fractional jitter first produced a permanent hold; integer-millisecond rounding
  restored a scheduled retry.
- Lease expiry during final writes and contradictory older same-version records
  both initially failed with “Missing expected rejection”; the final fences and
  whole-page version check made both green.
- Unknown validation-error payload initially classified as a typed refusal;
  closed shape checks now classify it as invalid response.

At source head `e29e14c`, direct local verification:

- Existing core runner: 336 passed, zero skipped/failing. The 71 new incremental
  tests were executed separately; register all four new test files in the union
  core runner (`incremental-wire`, `incremental-state`, `incremental-transport`,
  `incremental-coordinator`).
- Incremental component suite: 71 passed, zero skipped/failing. Includes a full
  injected-fetch → transport → coordinator → Dexie transaction lost-response retry,
  and durable cursor/projection/journal preservation assertions.
- Web, offline and kernel TypeScript checks passed.
- Touched ESLint/Prettier, repository contract verifier and `git diff --check` passed.

Commands (repository root, installed exact-lock dependencies):

```sh
node apps/web/tools/run-core-tests.mjs
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.kernel-test.json --pretty false
node --test apps/web/tests/access-kernel/incremental-{state,wire,transport,coordinator}.test.mjs
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.json --noEmit
node node_modules/typescript/bin/tsc -p apps/web/tsconfig.offline-check.json --pretty false
```

These tests use fake IndexedDB and injected responses, not native browser or
PostgreSQL proof. Exact-tree union review, genuine server/PWA journeys, old live
bundle/SW preservation and restore qualification remain required. Existing
physical Windows/Android, screen-reader and real operator gates remain unchanged.
