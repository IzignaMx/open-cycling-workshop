# One-shot connection ownership measurement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Independent concrete design review precedes TDD; exact-source workflow/guard review precedes the single coordinator dispatch.

**Goal:** Prepare a non-auto-running, two-case synthetic ownership measurement with closed evidence.

**Architecture:** A small host supervisor reuses unchanged containment primitives; one in-worker owner controls the concrete child and reserved observer. Separate closed receipts never impersonate the full Python suite.

**Tech Stack:** Existing Python/psycopg/SQLAlchemy, Linux pidfds, fixed Docker envelope, mocked deterministic pytest; no dependencies or privileges added.

**Spec:** `docs/superpowers/specs/2026-10-29-quote-ownership-measurement-design.md`.

## Global constraints

Exactly H once and conditional S once, no dispatch or financial writes. Setup65s
starts before the fresh API guard and includes observer reserve; GO starts host26s including observer close/reap; case
D8 starts before child creation; S only has <=5s post-D observation. Primary55s,
independent60s, outer1020s/job55min unchanged. Worker aggregate768MiB/1CPU/64PIDs;
PG1024MiB/1CPU/128PIDs/data512MiB. Canary create15s, otherclients5s maximum.
Local preparation/tests only; never run H/S, Docker, DB or real process fault cases
through routine pytest. Parent owns workflow/guard, publication and single dispatch.

## Current role/venue implementation gate

The original pending-role checkpoint is frozen in pure-only evidence. Bounded
scope now permits unchanged project initializer to create ordinary `ocwp` and its
`ocwp` database in this disposable fixture only. Exact COPY-only derived PG image,
synthetic file materialization, shared60s PG preparation bound and separate truthful
preflight require independent design acceptance before code. No bootstrap demotion,
real installation change, actual role SQL or H/S execution is permitted in routine
TDD. Parent retains the one authorized final dispatch after full source review.
First dispatch is consumed even on setup failure or unknown guard outcome.

## Review focus

- Reserved observer/GO race must not extend setup or create children early.
- PID reuse, wrong backend_start or stale observer snapshot must never prove absence.
- Oversized/partial/replayed IPC and output must stop without secret leakage.
- A blocking consumer or failed reap cannot acquire extra cleanup allowance.
- Independent container absence cannot rewrite a failed measurement as passing.

## Historical implementation checklist

The original Tasks1–4 below preserve the preimplementation sequence. Their unchecked
boxes are historical; the current completed preparation checkpoint below supersedes
them. Hosted qualification and the single dispatch remain live unchecked gates.

## Task 1: Closed protocol and evidence, tested without runtime effects

**Files:** create `scripts/ci/quote_ownership_evidence.py` and
`tests/operations/test_quote_ownership_measurement.py`.

**Interfaces:** `validate_frame(value: object, *, role: str, stage: str,
identity: dict[str, object]) -> dict[str, object]`;
`validate_receipt(value: object, identity: dict[str, object]) -> None`;
`write_receipt(path: Path, value: dict[str, object]) -> None` with16KiB cap.
No process/network imports with effects; no public plugin SDK exports.

- [ ] Obtain independent acceptance of concrete design, including GO deadlines,
      connection continuity and exact finite protocol schema before code.
- [ ] Write RED closed-schema tests for unknown/duplicate keys, bool-as-int,
      invalid identity/timing/order, >4096-byte frames, >16KiB evidence, unknown
      absence/reap, failed-H/S-skipped and failure-preserving final cleanup.
- [ ] Implement minimal fixed validators/codec, then GREEN; freeze finite fields
      and error vocabulary before runtime adapter implementation.

## Task 2: Concrete owner/child/observer with dependency seams

**Files:** create `scripts/ci/quote_ownership_worker.py`; extend the same test module.

**Interfaces:** guarded `main() -> int`; `run_owner(...fixed identity/deadlines...)
-> dict[str, object]`, `run_child(...) -> int`, `run_observer(...) -> int`.
Private adapters own process handles/pidfds, bounded IPC and fixed read-only SQL;
no arbitrary callable command selector, external DB URL or retry parameter.

- [ ] Write RED deterministic fake-clock/process/connection tests: no admission
      before reserved observer+GO; deadline starts before spawn; H late stop fails;
      S waits pre-dispatch until originalD; no restart/third child; observer
      shutdown/reap fits26s; malformed IO/pressure/identity/reap stops all admission.
- [ ] Add fake-driver continuity tests: same direct DBAPI object after SQLAlchemy
      initialization, identity transaction completed, bound clean Session, no
      reconnect; observer fresh snapshot exact tuple, never PID-only/timeout absence.
- [ ] Implement the concrete consumers with injectable private syscall/DB seams,
      Linux pidfd-only owned signals, bounded reads and fixed query allowlist.
- [ ] Run tests GREEN with all process/socket/DB effects mocked; assert import and
      normal pytest cannot call real entrypoints. No actual H/S execution.

## Task 3: Small contained orchestrator and distinct finalizer

**Files:** create `scripts/ci/quote_ownership_measurement.py`; extend tests.
Existing `quote_capacity_micro.py`/`verify_v01.py` behavior stays unchanged.

**Interfaces:** `supervise_measurement(worker_image: str, pg_image: str,
commit: str, evidence: Path, owned: Path) -> None` and
`finalize_measurement(...same identity paths...) -> None`; fixed CLI modes only.
Coordinator supplies reviewed guard receipt/identity, not a caller-selected command.

- [ ] Write RED fake-client tests for exact resource args/readback/owner manifest,
      same inherited absolute host setup deadline (guard included, never reset),
      observer reserve and canary15/other5 clipping, GO26 watchdog, uncertain create,
      failed observer reserve (zero H/S), bounded primary55/finalizer60 cleanup and
      independent failure-preserving final receipt. Assert full-suite selectors,
      schemas, argv and original controller source are unchanged.
- [ ] Implement only narrow primitive composition and fixed measurement launch;
      no full-supervisor copy, callback selector or fake pytest receipts.
- [ ] Run GREEN deterministic tests plus existing containment/controller/cleanup
      contracts. No actual Docker, process lifecycle or DB attempt.

## Task 4: Review and source-bound handoff, not execution

**Files:** above design/plan, execution-state and checklist; coordinator separately
owns dedicated manual workflow/guard and its adversarial review.

- [ ] Record actual RED/GREEN commands/results; run lint/types, repository contract,
      relevant regressions and full locked Prettier after final docs. Retain all
      prior local full-suite/historical diagnostic failures; no capacity reruns.
- [ ] Independently review resource/IPC/identity/privacy/stop paths and manual-only
      workflow guards, pin exact source/tree/workflow numeric ID and authorization.
- [ ] Freeze local patch/hash/evidence for coordinator. No remote writes or dispatch
      during preparation. The release coordinator alone checks quiet queue, holds publications,
      performs the one authorized dispatch and verifies terminal owned cleanup.

## Reviewed pure-only execution checkpoint

Independent checkpoint accepted pure validators/codec and fake-clock gate tests
only. The design's frozen field/event tables are normative before TDD. Implement
`decode_frame(raw: bytes, identity: dict[str, object]) -> dict[str, object]`,
`encode_receipt(value: dict[str, object], identity: dict[str, object]) -> bytes`,
`decode_receipt(raw: bytes, identity: dict[str, object]) -> dict[str, object]` and
`MeasurementGate(setup_started_ns: int)` with `reserve(now_ns)`, `go(now_ns)`,
`admit(case, now_ns)`, `finish(case, passed, now_ns)`, `close_observer(now_ns)`.
Use no writer/process/network/DB API in this increment. The original Task1 writer
is deferred until fixed path ownership is reviewed. Tests must explicitly show
that read-only/backend/reap booleans are validated claims, not measured runtime
facts; release coordinator API guard and dependent consumer remain separate pending work.

## Historical pure preparation evidence · 2026-10-29 (before role clarification)

No H/S, Docker, DB, role creation, child stop, actual IPC or API fetch has run.
Initial codec RED: missing module at collection. Bounded stream RED: two missing
stream tests; fresh-H/S-incarnation RED: one accepted-reuse defect; terminal-stream
RED: two accepted FAIL→GO/close-before-READY defects. Each was corrected and the
pure suite now passes65 cases. Strict mypy, Ruff check/format pass for the codec.
The separately implemented guard's135 tests also pass; combined200 pure cases.
These validate synthetic claims and mocked chronology, not runtime facts.

At this frozen checkpoint the ordinary-role authority blocker remained, as did
concrete consumer/controller,
fixed evidence-path ownership, exact workflow registration/source and final review.
Do not publish this as an unused standalone protocol increment or interpret pure
GREEN as permission to dispatch. The one-shot remains unconsumed.

## Initializer adaptation review (now accepted for mocked implementation)

- [x] Obtain independent source review of the design's unchanged initializer
      SHA256, image COPY-only synthetic file, fixed postgres-bootstrap/ocwp-app
      identities, shared60s image preparation and setup65s preflight reservation.
- [x] After acceptance, extend mocked TDD for the concrete worker/controller;
      no tests may execute SQL, actual child stop or H/S. Preserve frozen pure
      package and all RED logs; no automatic workflow or consumed trial rerun.

## Concrete adapter interfaces (mocked implementation accepted)

Initializer/venue adaptation and shared guard-inclusive65s are independently
accepted for mocked implementation, not execution. Split the fixed DB seam into
`scripts/ci/quote_ownership_database.py` (preflight, clean direct Session, observer)
and its pure mocked test module. No production service or full-suite controller
is changed. The synthetic fixture value is public and used only in disposable
image/database construction; never echo it into closed evidence.

`quote_ownership_worker.py` provides `run_owner(adapter, identity,
setup_deadline_ns)`; adapter clock/owned-process/channel/DB operations are fully
faked by tests. Actual adapter exists only behind fixed `main()` owner/child/
observer modes. `OwnedProcess` opens retained pidfd before accepting READY,
corroborates Popen PID/start ticks and signals only pidfd, reaping under the
original deadline. `PipeChannel` uses capped length-prefix frames with bounded
nonblocking reads/writes and allowlisted FD inheritance. No arbitrary command,
query, module or external URL input.

The owner emits one final closed observation (not container-cleanup qualification):
exact identity, setup/elapsed, observer and two case records, status observed/failed
and fixed failure. Supervisor supplies independently sampled cgroup resources and
primary cleanup; finalizer supplies distinct exact-owned absence. Shared lifecycle
validation is reused without inventing resource values or a fake passing receipt.
This necessary observation envelope is frozen/RED-tested before consumer code.

## Current concrete local checkpoint · 2026-10-29

- [x] Author fixed worker/controller/finalizer and manual venue with mocked adapters,
      preserving original guard-inclusive setup65 and experiment26/cleanup55/finalizer60.
- [x] Reproduce and correct rejected-stream/backend/OS-identity boundaries, partial
      IPC/EINTR/FD disposal, observer BEGIN/order/rate, captured late signal, and
      anchored receipt hardlink/ancestor safety with retained RED logs.
- [x] Mock owner→primary cleanup→independent cleanup→final receipt/hash, retaining
      source and cleanup failures; dangling owner symlink is unknown.
- [x] Complete final combined mocks/static/format and concrete independent source review.
- [ ] Complete exact-source hosted normal qualification before one-shot dispatch.
- [ ] Coordinator alone dispatches once after final guards/review, then assesses
      closed terminal evidence. No local or routine-CI H/S rehearsal is permitted.

The initial200-case pure snapshot remains historical. Current component counts
are preparation evidence only (89codec,38DB,42worker,31controller,230venue helpers);
no real connection lifetime, pidfd signal, role initialization or absence is proved.

Final local source review accepted the concrete controller/worker and fixed cleanup
binding. Combined430 ownership mocks and715 including existing containment tests
passed; strict mypy8 source modules and Ruff18 source/test files passed. These are
nonconsuming preparation checks, not the hosted measurement or its qualification.
