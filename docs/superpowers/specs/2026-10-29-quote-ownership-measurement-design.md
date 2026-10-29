# One-shot quote connection ownership measurement

Assistant-selected implementation design under the approved bounded two-case
measurement scope, 2026-10-29. Baseline main
`0726b9221bfbdffd708c7dbb7d456ee0771a6791`, tree
`b7a55e46535beecd65db68ec01639d8529d5bc81`. Frozen proposal SHA256
`1951f853a6e6cb1f57d0f66501726cfa370c33e9dd167b9f9a118aae463b8971`.
Design review precedes harness implementation; exact-source qualification and
release coordinator dispatch gates precede execution. No measurement has run. The disposable application-role scope was subsequently clarified as described
below; initializer/venue adaptation is independently accepted for mocked
implementation, with final concrete source review still required. This design draft alone does not authorize runtime execution.

## Venue and scope

A dedicated workflow_dispatch-only hosted job, contents:read, no automatic trigger,
new credential, grant, privilege or network route. Coordinator owns workflow/API
at-most-once guard implementation and publication/dispatch: fixed authorization ID,
workflow path and independently pinned numeric ID, run_number=1/run_attempt=1,
exact repository/ref/source/tree, complete unfiltered history, same-job guard
immediately before setup. Fail closed on ambiguity; the first dispatch is spent even if setup fails or the
guard outcome is unknown.
Concurrency alone is not a consumption lock. The coordinator holds the publication
queue and checks other workflows are quiet; this is not an atomic global reservation.
No local Docker is available; do not substitute another venue or execute H/S in tests.
The release coordinator has reserved the OCW publication/dispatch queue through terminal owned
cleanup. History/ordinal guarantees rely on retained GitHub workflow identity;
administrator deletion/recreation or history mutation is not an immutable boundary
and requires a stop/review, never rotation of identity to regain an attempt.

Two cases only, H then S conditional on complete H success. No quote dispatch,
financial writes, migrations, large fixtures, sleeps in SQL or backend termination
query. One fresh child at a time and one reserved same-role read-only observer.
One worker cgroup includes idle container process, owner, child and observer:
768 MiB, 1 CPU, 64 PIDs total. PG: 1024 MiB, 1 CPU, 128 PIDs, data tmpfs512 MiB.
Existing scratch/shmem/security/network/image/preflight/canary controls stay fixed.
Worker+PG memory1792 MiB/2 CPU is a subtotal, not host or production sizing.

## Disposable-role adaptation and retained blocker history

The initial frozen pure-only checkpoint was blocked: existing Docker initialization
with `POSTGRES_USER=ocwp` creates PostgreSQL18.4 bootstrap superuser, not an ordinary
application role. Bootstrap SUPERUSER cannot be demoted; no ALTER ROLE workaround
was attempted. That pending-role checkpoint remains in the frozen pure evidence.

Current bounded scope permits the project's existing initializer to create its
ordinary application role only inside this disposable fixture, destroyed with the
owned environment. No real installation user/grant, migration or financial write
is changed. The initializer/venue design is independently accepted for mocked implementation;
no role SQL or H/S has run.

Use byte-identical `infra/compose/postgres-init/10-application-role.sql`, SHA256
`bab26657f57af9679b470f9fdf6c4efee4e767bd9c601903debb911b2b1f62f8`.
It expects a >=32-character `/run/secrets/postgres_password` file, creates LOGIN
`ocwp` with NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION, creates database
`ocwp`, revokes PUBLIC database access and grants that role CONNECT. Its existing
SQL remains unchanged; these disposable initialization actions are the scoped
exception to the original no-new-role setup, not permission for arbitrary grants.

Proposed fixed fixture image: derive from exact existing postgres18.4-trixie image,
COPY the initializer into `/docker-entrypoint-initdb.d/10-application-role.sql`
and a clearly public synthetic fixture value >=32 characters into the required
secret-file path during image preparation. No SQL/RUN at image build; no host bind,
new tmpfs or writable root. Bootstrap `postgres`/database `postgres`, then use only
ordinary `ocwp`/database `ocwp` for observer/child. Same cgroups/scratch/closed-network
and logging-none settings remain. Bind derived image and source label plus exact
base image identity in reviewed preparation evidence. Fixture text is not a real
credential and must never be printed in diagnostic receipts.

Proposed image-preparation bound: existing PG pull plus COPY-only fixture build
share the current60s PG preparation window and unchanged enclosing image/job
ceilings, no extra allowance. Insufficient time stops preparation. Reviewer must
accept this bound and image/readback identity before implementation.

Do not call `_full_worker_preflight`: its hardcoded role/database
`ocwp_quote_full_test` would misstate this fixture. Add a separate fixed measurement
preflight retaining the same tool/version/PGsettings checks, then verify current
role/database, all four administrative flags false and active read-only status
through the ordinary connection. Temporary preflight connections close before
observer reservation, all within setup65s. Routine tests mock these operations;
no actual initializer or child/observer executes before final one-shot review.

## Reuse without a generalized full-suite controller

Import existing narrow primitives from `scripts/ci/quote_capacity_micro.py`:
`full_client`, `full_role_limits`, `full_inspect`, `full_scratch`,
`effective_privileges`, `cancellation_canary`, resource parsing/probes,
narrow `remove_owned` and containment readback helpers. Measurement cleanup uses
its own immutable `_reconcile_fixed` binding, not mutable-manifest `full_reconcile`. Reuse
immutable `FULL_POLICY`, `FULL_TMPFS`, PostgreSQL settings and image pins.
Use a measurement-specific preflight preserving required versions/settings with
the reviewed ordinary-role/database identity, never the old hardcoded full-suite
assertion. Temporary connections close before observer reservation and admission.

Do not call/generalize `supervise_python`, `finalize_python`, `full_python_args`,
full-suite identity/shard selection or collection/result validators. Do not copy
the ~500-line supervisor. A measurement-specific orchestrator implements only
creation/preflight, one fixed owner command, bounded output and cleanup. A small
fixed container-argument builder may reuse constants without changing old callers;
if extraction is necessary, it is limited to exact-equivalent resource creation
and needs separate regression proof before changing the existing caller.
Measurement identities/receipts/finalizer are distinct; they cannot satisfy a
full-Python qualification schema.

## Setup, admission and finite schedule

The trusted same-job shell mints one absolute host monotonic nanosecond
`OCWP_OWNERSHIP_SETUP_DEADLINE_NS` at now+65s BEFORE the fresh API setup guard.
Guard work consumes that original65s; its own45s maximum is clipped to remaining
setup time. The supervisor inherits the same deadline, never starts a new65s
after guard. Reject malformed, expired or impossible >65s remaining values.
Source/image/containment preflight and observer reservation share what remains. Canary create alone may use15s, every other Docker/Git client <=5s,
clipped to remaining setup time; canary must be removed before admission.

Start the owner inside the existing worker before setup ends. Owner runs fixed
preflight and starts one observer subprocess. Observer connects once to the fixed
synthetic database/role, read-only, obtains its own identity, and reports RESERVED.
Owner sends RESERVED to supervisor only after validating that response. Supervisor
must receive and validate it inside the original setup65s, then sends the single
GO frame. Missing/late reserve or GO means no H/S admission and owned cleanup.
This handshake is not an extra startup allowance.

At GO send, host begins its independent <=26s measurement watchdog. At GO receive,
owner begins its own <=26s deadline before first child admission; the stricter
host watchdog still applies. Each case's original D=t0+8s starts immediately
before creating its fresh child, never after READY. H must close, reap and prove
fresh exact backend absence by D. S must reach READY before D, remain blocked on
its private control pipe (no dispatch), with the owner requesting stop at D and
recording the actual request time within the unchanged D+5 window. Only S
has <=5s post-D observation/reap window, clipped to remaining shared26s.

Observer close and reap, inter-attempt handoff, messages and final evidence are
inside26s, not a new teardown window. Stop admitting after any failed/unknown
condition. No retries, replacement child/observer or reuse of unused allowance.
The configured setup65 + experiment26 + primary cleanup55 =146s; independent
finalizer <=60s gives206s scheduling envelope after image preparation, not a
promise under OS stalls. Existing outer1020s/job55min remain enclosing fail-safes.
Image builds keep existing separate ceilings; ordinary suite900s is not extended.

## Concrete child/observer ownership and IPC

All process/DB creation is behind explicit runtime entrypoints and an authorized
contained invocation. Imports and ordinary pytest never spawn these consumers.
Use direct fixed argv, no shell/selector/module supplied by a caller. Fixed worker
roles are owner, child and observer; only the measurement CLI can select them.

Owner retains Popen handles plus Linux pidfds for children/observer. Opening a
pidfd is mandatory; no PID-only kill fallback. Signals target only the retained
owned pidfd, never broad groups or PostgreSQL PIDs. Reap each owned process;
missing identity/reap proof is terminal unknown. Failure of in-worker ownership
cleanup delegates to existing exact-container external cleanup, not a new kill.

Length-prefixed UTF-8 JSON frames: maximum4096 bytes/frame, exact closed keys/types,
no duplicate keys, finite stage/source/attempt binding and no arbitrary text.
Nonblocking bounded reads/writes use remaining monotonic deadline; EOF, partial,
oversized, duplicate/out-of-order/wrong-owner frames fail closed. Only one pending
observer query at a time, at most256 absence checks per case, minimum50ms between
checks; no indefinite polling. Bounded protocol counters are not timing guarantees.
Child control accepts CLOSE for H or a continued pre-dispatch wait for S, never
DISPATCH. Owner/observer shutdown consumes remaining26s and cannot restart it.

Child opens one direct psycopg connection to the fixed synthetic database/role
with read-only session default. Bind SQLAlchemy Connection to that same driver
connection using NullPool/no reconnect. Complete initialization/identity reads,
explicitly commit the read-only transaction, then construct Session bound to the
same Connection with autobegin disabled. Verify driver-object continuity, exact
PID/backend_start/database/role identity and no transaction before READY. Keep
that owned connection alive while waiting. Any identity/transaction discrepancy
fails; no reconnect may repair it. CLOSE closes Session/Connection and exits.

Observer is one persistent same-role read-only autocommit connection. Every query
is a fresh observation of exact PID AND backend_start AND database AND role;
never infer absence from PID alone, a stale snapshot, connection error or timeout.
Observer never calls termination/cancellation SQL. Backend metadata is not a
financial row. Child/observer fixed database parameters remain private, never in
messages, receipts, argv URLs or logged exceptions.

## Closed evidence and qualification

Separate `ocwp.quote_ownership.receipt` and independent-cleanup kind, schema1;
maximum16 KiB each, exact keys/types/fixed failure vocabulary, source/tree/image/
run/authorization/ownership binding. Record H/S once or skipped-after-failure,
fixed stages, monotonic durations, child PID/start identity, exact backend identity,
reap/absence flags, cgroup peak/counters/process counts and cleanup disposition.
No SQL, credentials, URLs, exception/free text or application data. Preserve raw
failure classification only through allowlisted codes, not `str(error)`.

A successful receipt requires all containment gates, H complete by8s, S readiness
before8s and owned stop/reap/fresh absence within its fixed window, observer
close/reap by26s, no pressure, and independently verified exact owned containers
absent. Any malformed/unknown/late condition is terminal failure, not an excuse
to resize/retry. The independent finalizer may prove absence after measurement
failure but must never convert that failure into passing.

This measures tiny clean-session continuity and pre-dispatch stop aftermath only.
No production A/C, concurrency/child RAM sizing, actual quote success, in-flight
query/COMMIT cancellation, network partition, hard cutoff, owner-crash recovery,
capacity, physical acceptance or public activation is qualified.

## Frozen pure preparation contract

This section is accepted preparatory scope only: no real child/DB entrypoint yet.
Coordinator owns the separate API/workflow guard. Validators consume its trusted,
reviewed expected identity, never treat an untrusted receipt identity as authority.

Identity exact keys: `commit`, `tree` (40 lowercase hex), `worker_image`, `pg_image`
(`sha256:` +64 lowercase hex), `authorization`, `nonce` (32 lowercase hex),
`run_id`, `workflow_id` (positive decimal strings <=20 digits), `run_number`,
`run_attempt` (integer1), `repository`, `repository_id=1327018760`, `workflow_path`,
`ref`, `database`, `role`.
Repository is `IzignaMx/open-cycling-workshop`, ref `refs/heads/main`; workflow path
is `.github/workflows/quote-ownership-measurement.yml`; authorization is the frozen
proposal SHA256 above, corroborated by the coordinator. Database/role are bounded
ASCII identifiers. Runtime database/role are fixed `ocwp` after the reviewed initializer; pure
fixtures may use a distinct mocked identity but cannot establish runtime authority.

Frame wire is a four-byte unsigned big-endian payload length followed by exactly
that many JSON bytes; the4096B cap includes the prefix. Receipt bytes are plain
JSON with the16384B cap.

Frame exact keys: `schema=1`, `kind=ocwp.ownership.frame`, `identity`, `sender`,
`case`, `sequence`, `event`, `payload`. Sender is host/owner/child/observer; case
setup/H/S/teardown; sequence integer1..520, monotonically increasing per sender/
case, never reused. Total observer polls <=256 per case. Event/payload table:

| Event    | Sender/case                  | Exact payload                                                          |
| -------- | ---------------------------- | ---------------------------------------------------------------------- |
| RESERVED | observer or owner/setup      | `read_only=true`, `transaction_idle=true`                              |
| GO       | host/setup                   | empty                                                                  |
| READY    | child/H or S                 | `backend`, `read_only=true`, `clean_session=true`, `same_backend=true` |
| CLOSE    | owner/H or teardown          | empty                                                                  |
| OBSERVE  | owner/H or S                 | `backend`                                                              |
| OBSERVED | observer/H or S              | `backend`, `present` bool, `read_only=true`, `transaction_idle=true`   |
| CLOSED   | child/H or observer/teardown | empty                                                                  |
| FAIL     | any sender/case              | `code` from fixed failure enum below                                   |

Backend exact keys: `pid` integer1..2147483647, `start_us` positive int64,
`database`, `role` equal reviewed expected identity. Process identity is separate
from backend PID; validators never authorize killing a backend.

Receipt exact keys: `schema=1`, `kind=ocwp.quote_ownership.receipt`, `identity`,
`status`, `failure`, `setup_ns`, `elapsed_ns`, `observer`, `cases`, `resources`,
`primary_cleanup`, `independent_cleanup`. Status pending_cleanup/passed/failed.
Cleanup enum pending/verified_absent/unknown; failure is null only for passing or
pending-cleanup observations. Codes: preflight, role_unverified, protocol,
setup_deadline, experiment_deadline, case_deadline, identity, observer_unknown,
reap_unknown, pressure, interrupted, cleanup_unknown. No arbitrary exception text.

`observer` exact keys `reserved`, `read_only`, `transaction_idle`, `closed`,
`reaped` (bool). `cases` is exactly two ordered records H then S. Each case exact
keys `name`, `status` (passed/failed/skipped), `backend` (tuple above or null),
`start_ns`, `ready_ns`, `stop_ns`, `reaped_ns`, `absent_ns` (nonnegative int64 or
null), `read_only`, `clean_session`, `same_backend` (bool). Timestamps are relative
to GO; D=start_ns+8e9. Passed H requires start<=ready<=stop<=reaped<=D and fresh
absence after stop byD. Passed S requires ready<D, stop>=D, stop/reap/absence<=D+5e9;
actual stop lateness is stop-D, never a guarantee of exact8.000s delivery. Both
require true read-only/clean/continuity and backend identity; absence may precede
reap but follows stop. H failure/skipped forces S skipped; no later admission. Passed H/S must name
different backend incarnations; reusing the same PID/backend_start tuple is refused.
Skipped records have no backend/timestamps and false evidence flags.

`resources` exact keys: `worker_peak_bytes`, `pg_peak_bytes`, `worker_processes`,
`pg_processes`, `pressure_events` (nonnegative ints). Peaks <=768/1024MiB, process
counts <=64/128, pressure zero required for success. Sum of recorded cgroup peaks
is a conservative combined peak upper bound, not an atomic simultaneous sample.
Observed success requires both cases passed, setup<=65e9, elapsed<=26e9 covering
all timestamps and observer close/reap. Overall passed additionally requires both
cleanup fields verified_absent; independent absence cannot erase any failed case.
Failed receipts retain partial evidence but never become passing just from cleanup.

Byte decoding rejects duplicate keys before dict construction, floats/nonfinite
values, numeric tokens >19 digits, invalid UTF-8 and non-object roots. Exact types
exclude bool-as-int. Frame4096B/receipt16384B caps apply before parsing and after
encoding. At the historical pure checkpoint no file writer was added. The concrete writer
now uses anchored directory FDs, no-follow single-link checks and atomic replacement;
source review and filesystem mocks do not establish hosted ownership.

Private pure `MeasurementGate` consumes injected monotonic nanoseconds only:
setup→reserved exactly once→GO exactly once→admit H→finish H success→admit S→finish
S→observer close. Any failure/late transition closes admission permanently;
finish failure permits cleanup only, not S. Setup clock begins at construction;
GO cannot occur after65s;26s clock starts at GO and never renews. Per-case D begins
at admit, before the future process spawn. Nonmonotonic clocks, duplicate GO,
wrong case/order and late successful finish are rejected. All syscall, SQL,
pidfd-target and read-only runtime proofs remain future reviewed adapter work,
not facts established by these pure tests.

`FrameStream(identity, sender, case, backend=None)` is a pure per-owned-pipe
receiver for the planned adapter, not a process owner. `accept(raw)` applies byte
validation then exact prebound sender/case and sequence1,2,... (no gaps/replay).
RESERVED/GO/READY/CLOSE/CLOSED/FAIL are each at most once per stream; OBSERVE and
OBSERVED each at most256. A prebound expected backend tuple must match any frame
backend exactly (including backend_start), not only its PID. Any refusal or accepted FAIL/CLOSED frame terminates
the stream permanently; child CLOSED is accepted only after READY. The consumer must bind child READY identity into the
observer stream; this pure mechanism does not observe real backend presence.

## Pure OS-ownership schema extension (before concrete consumer)

Preserve the accepted initial pure snapshot. Add required `process` to each case
and observer: null only for skipped/not-started evidence, otherwise exact keys
`pid` integer1..2147483647, `start_ticks` positive int64, `pidfd_owned` bool.
Passed cases and reserved observer require true pidfd_owned; record the retained
Popen PID plus separately read start ticks, never a PID-only kill permission.
H/S process incarnations must differ, as must each child from its observer.
A supplied pidfd_owned flag remains a claim until the future adapter proves it.

Observer additionally has `reserved_setup_ns`, `closed_ns`, `reaped_ns` (nullable
nonnegative int64). Successful evidence requires reserve<=setup_ns, then
0<=closed<=reaped<=elapsed<=26s after GO; both cases have finished before observer
close. A skipped observer has no process/timestamps or true lifecycle flags.
Failed receipts may retain incomplete known facts, never infer reap/absence.

Pure `parse_process_identity(raw: bytes, expected_pid: int) -> dict[str, int]`
accepts <=4096 bytes of `/proc/<pid>/stat` supplied by a future adapter; it performs
no filesystem/process syscall. Parse numeric PID prefix and the final `) ` delimiter
before fixed state/numeric fields, not whitespace splitting of comm. Process comm
can contain spaces/parentheses and is discarded, never logged. Match expected PID;
validate state and field22 start_ticks as bounded exact integers. Malformed/truncated
records fail fixed-code without echo. Concrete adapter must obtain pidfd immediately,
corroborate the retained Popen identity and recheck start ticks without reopening or
signalling by PID fallback; actual timing/FD ownership awaits runtime review.

Owner final frame extension: RESULT, sender owner/case teardown, at most once,
exact payload keys `status` (observed/failed), `failure`, `setup_ns`, `elapsed_ns`,
`observer`, `cases`. It carries no invented cgroup/cleanup facts. The shared
lifecycle validator enforces the same identity, timing, OS/backend and observer
conditions for observed as the final receipt; failed preserves partial facts.
Supervisor validates this observation before adding independently sampled resource
facts and owned cleanup. Accepted RESULT is terminal on its stream. The owner's
setup timer is derived from the inherited absolute setup deadline minus65s;
GO and all temporary setup connections remain inside that original budget.

Reserved observer receives exactly one BEGIN frame from owner/setup after host GO,
with sole payload `experiment_deadline_ns` positive int64. That is the already
started owner GO+26s deadline, not now+26 on receipt. It must arrive inside original
setup65; reject expired/impossible >26s remaining deadlines. No BEGIN is permitted
before host GO or more than once. This prevents an observer from remaining on an
obsolete setup deadline during H while forbidding renewed lifetime. Host26 watchdog
remains independently stricter. All channels close unlisted descriptors; child and
observer processes inherit only their own stdin/stdout control pipes.

Pure `identity_from_environment(env)` constructs the expected identity from the
trusted same-job context and reviewed pins, not a result's self-reported identity:
GITHUB_SHA must equal OCWP_EXPECTED_SOURCE_SHA, repository/id/ref and run ordinal/
attempt are exact; tree/workflow ID use reviewed pin variables; image IDs/nonce use
fixed preparation outputs. Database/role are fixed ocwp. Runtime still requires
fresh guard-setup binding to match this identity plus exact clean checkout/image
readbacks. Environment agreement alone is not API verification or review approval.

Finalizer artifact `cleanup.json` closed keys: schema1,
kind `ocwp.quote_ownership.independent_cleanup`, identity (full binding or null
before ownership), expected_commit, run_id, run_attempt, owner_manifest_present
(bool), owner_token (nonce or null), outcome verified_absent/not_started/unknown,
elapsed_ns, receipt_sha256 (final receipt hash, or null when no receipt exists
or cleanup is unknown and no trustworthy final byte binding can be claimed).
Verified absence requires exact full identity/nonce, manifest present and <=55s
internal cleanup; not_started requires no manifest and never promotes a receipt.
Unknown retains failure. Early incomplete context remains nonqualifying; caller
must compare source/run metadata with trusted environment before publication.

`fixture-preparation.json` closed keys: schema1,
kind `ocwp.quote_ownership.fixture_preparation`, full identity, pg_base_image
(immutable config ID), pg_base_reference (official postgres@sha256 manifest), and
files with exactly dockerfile/initializer/public_fixture SHA256 hashes. No values,
SQL or raw logs. `validate_cleanup(value, identity_or_none)` and
`validate_fixture_preparation(value, identity)` are pure shape/binding validators;
file ownership, source/run context and actual absence are established by the
fixed finalizer/stager, not the JSON validator alone.

## Current local preparation checkpoint · 2026-10-29

The concrete worker, fixed host controller/finalizer and dedicated manual workflow
are now authored; this supersedes earlier future/pure-only implementation wording,
not historical test evidence. No H/S, Docker, role SQL, real child stop or API fetch
has executed in authoring tests. Current component mocks: codec89, DB38, worker42,
controller31 and guard/adapter/images/staging230; combined430 tests and complete concrete source review passed. A separate bounded
combined run with existing containment tests passed715; hosted qualification and
the single measurement remain pending. Worker review includes retained pidfd/Popen
identity, mandatory observer BEGIN after GO, H before S, expected exit status and
separate OS-reaped/descriptor-disposed facts. All observer polls are globally at
least50ms apart, including initial presence and first absence, without reset.

A signal request later than requested D8 may support only this bounded observation
when actual request/reap/absence remain within original D+5 and experiment26.
Record observed send time; never claim exact OS scheduling or hard8 cancellation.
A late wait or ambiguous descriptor close is nonqualifying, with only remaining
original time and exact outer-container cleanup; no new window or leak-proof claim.

The ordinary-role database predicate refuses any database-connected session with
`datname IS NOT NULL AND usename IS DISTINCT FROM current_user`. It uses visible
PG18 fields, not cross-role backend_type (which can be masked). This is not proof
of absence of every privileged internal process. No privileged observer is added.

The finalizer preserves failed measurement status even after verified owned absence.
Missing or suspicious ownership metadata is unknown, not guessed absence; genuinely
not-started preparation has no owner manifest. Source rebinding failure remains
failed. Closed receipts use anchored atomic writes and strict no-follow reads;
publication stages only validated allowlisted metadata, never raw preparation logs.

Cleanup selection uses the immutable expected token/images/names, never a later
filesystem manifest reread as removal authority. CID files are anchored untrusted
hints only. Missing manifest with any remaining owned/CID hint is unknown. Final
staging rejects a passed receipt unless independent cleanup is verified and its
nonnull digest matches the exact final receipt bytes. Best-effort local metadata
downgrade after a late error cannot renew a runtime cleanup deadline. Process
counts are maximum sampled `pids.current`, not true process-count peaks; memory
uses cumulative cgroup `memory.peak`. Neither is a production sizing result.
