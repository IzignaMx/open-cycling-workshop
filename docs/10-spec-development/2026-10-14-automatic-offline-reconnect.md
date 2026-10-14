# Automatic reconnect after retained offline admission

Increment C correction, limited to the existing authenticated workshop slice.
A browser connectivity hint and its `online` event are advisory. Successful
retained offline admission must recover automatically when the API becomes
reachable, even if a reload lost the event or the hint stays true or false.

## Reproduced hosted boundary

Published PR38 head `70f16fc109cf2994903cd498f4589fb90db0aa3e`, tree
`094cbea2333504179635ec0cd1c17f1bd29639f5`, passed offline reload but failed two
of 27 direct browser cases during subsequent convergence. Customer/order work
remained pending and the UI stayed offline. In the customer trace, network was
restored after reload and no API request followed. Direct artifact `11922880494`
was verified against SHA-256
`e36d2cee7d5b4f0c4c8dbf24445e6843787550dd6ca20076a4bd433ef7159537`.

Local runtime run
[38620882894](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38620882894)
failed at `reconnect_and_convergence`, after six of eleven substantive checks.
Offline readmission advanced; restore and the remaining checks were not reached.
Artifact `11922517146` was ZIP/CRC/SHA-256 verified:
`4be380954a91287848abe72087da2403c1e2c84e89aac45f55ed5ee2b4ca97b0`.
All three ARM64 cross-builds passed. These are prior-head observations, not proof
of this correction, physical ARM operation or restore readiness.

## Bounded read-only reachability

A dedicated coordinator probes captured `/auth/me` only while the exact source
is READY/offline, its stored session matches the admitted source and the kernel
still accepts its owner, binding, scope, incarnation, monotone clock and lease.
Its timer is separate from ordinary sync. Delays are 2, 4, 8, 16, then at most
30 seconds; the lifetime ends at the original lease deadline. There is no
arbitrary eight-attempt cutoff that strands an otherwise valid long-offline
session. Duplicate offline notifications do not reset that backoff.

Each attempt has a ten-second deadline, clamped to the remaining original lease,
covering fetch and streamed body consumption. Deadline processing rechecks the
clock even if the transport has not settled. Cancellation aborts the request and
permanently fences late results. Single-flight ownership remains until the actual
probe settles, including a transport that ignores AbortSignal. Such an
uncooperative request may delay further probes; it cannot create overlapping
retries or revive its expired capture. Ownership is released before awaiting
subsequent authoritative verification, so an unrelated hung context handoff
cannot occupy a newer session's probe slot. Old finalizers cannot clear a newer
in-flight request.

Network failures/timeouts do not mutate authority, extend the lease, replace
ownership, clear pending work, or claim sync success. Kernel inspection may
advance the existing monotone clock observation; it does not renew authorization.
Bodies remain byte-bounded. Probe cancellation cleanup is best effort and does
not obscure an already received refusal or malformed response. Existing normal
bounded readers retain their prior cleanup behavior.

## Authority and concurrency fences

A complete valid `/me` is only a reachability hint. Its captured identity is
handed into existing expected-owner verification, followed by authoritative
`/auth/context`, and baseline preparation when required. No mutation/delta
transport is dispatched before that sequence. A received denial, invalid body,
changed principal or changed account scope is routed into expected-owner
invalidation and a visible hold; the client does not retry `/me` to overwrite
known refusal evidence or silently select a different workshop.

Current authoritative context acceptance records generation-bound reachability
before baseline preparation, allowing both an equivalent context and a required
new baseline to proceed despite a stale false browser hint. This observation is
separate from the verified-online authorization gate. Cancellation, identity or
workshop change, disconnect, expiry/hold/dispose and genuine network failures
clear it. Failed new-baseline preparation cannot restore old offline admission.
Explicit login, retry and manual sync behavior remains server-authoritative.

Every runtime source retains an exact session snapshot, refreshed synchronously
only by its own legitimate admission remember operation. Stored metadata changes
during an awaited claim, context request, preference copy or publication cannot
publish the previous account's READY view or dispatch its work. A disconnect
during READY preparation is reflected at publication: the source remains
offline and arms a read-only probe. Automatically scheduled sync also checks the
current source and verified-online state when it runs, so a stale true hint cannot
turn this race into destructive implicit verification. Native reconnect cancels
a pending probe; late completion cannot claim the newer owner again.

## Evidence and remaining gates

The no-event regression was observed RED with unchanged offline/pending status,
then GREEN through parsed context, immutable journal and durable applied ACK.
Independent review supplied additional RED reproductions for same-token metadata
replacement, post-remember publication, changed account scope, duplicate offline
backoff, lease/clock deadlines, preference-copy disconnect and handoff occupancy.
They are retained as regression tests. Deterministic tests also exercise recovery
after more than eight failures, stale false hints through both context reuse and
rebaseline, denial/nonsettling body cancellation, native reconnect, takeover,
logout, expiry/rollback and unchanged lease/history on unreachable probes.

Local TypeScript/emulated IndexedDB evidence does not qualify the actual browser
or Docker paths. The unchanged customer/order journeys must pass automatically
on the next exact hosted candidate, without extra test clicks or larger acceptance
timeouts. All eleven runtime checks, incarnation-rotated restore, existing native
and old-App/SW gates and actual screenshot inspection remain required. Normal
Compose activation and physical-device gates are unchanged.

The final local source checks pass 577 frontend core tests, including the 95-test
focused controller/transport/probe matrix, with zero failures/skips. The 24
repository contracts, web/offline TypeScript checks, web-source/runtime ESLint,
touched formatting/whitespace checks and production PWA build also pass. These
counts overlap; they are not a new full Python or hosted qualification aggregate.
Independent source review reproduced and closed the listed race findings; its
exact-tree record is retained with the publication handoff.
