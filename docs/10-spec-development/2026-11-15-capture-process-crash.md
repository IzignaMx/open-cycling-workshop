# Committed capture storage after an injected browser crash

## Decision and baseline

Verified baseline main `4d5cc51230168ef363877d09c5d659721e9b7b9e` has tree
`7fae8a2b0e6027b793c659f7f91d7b53fadb57c7`. The coordinator reports
[CI 43699706556 attempt 1](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/43699706556)
passed ten checks, 6,747 Python tests plus 58 expected skips, 1,579 frontend,
140 direct browser cases without retry, five App/SW/restart/engine cases and
three reducer cases without retry. Those results qualify the baseline, not this
new increment. Earlier dated pending entries remain historical records.

The next bounded integrity gap is recovery of committed synthetic storage after
an injected browser-main-thread crash, rather than the already-qualified orderly
shutdown. It contributes a narrow failure-mode observation toward G2/G3. It does
not establish handover, deployment exclusion, a rollback floor or physical V0.1
acceptance. No production data, schema, runtime, selector or format changes are
part of this increment. Shared-origin production writes remain v1.

## Crash and recovery boundary

Keep the two graceful restart cases and two reload cases unchanged. New separate
old/current scenarios use the same exact source/lock/App/SW provenance, owned
synthetic profiles and pinned Chromium engine. The first process installs the
actual App/SW and reaches its existing post-maintenance barrier. Synthetic writes
await transaction completion and are read back before the fault.

The fixture distinguishes **UNSENT** content from a separate **PROTECTED**
checkpoint. Protected-channel private content is absent by contract; recovery
must not recreate it or rearm that checkpoint. Existing UNSENT future payload,
v1 customer, absolute timestamps, journal and maintenance witness remain separate
controls. A locked App retaining protection metadata is not authenticated command
replay qualification.

The first page is staged at `about:blank` before the fault. This avoids restoring
an active App ahead of offline admission, but narrows the claim: it is recovery
after committed storage and inert-page staging, not interruption during an App
edit or immediate-write durability. Export the first trace before the crash;
there is no reliable post-crash trace from that process.

The fault is exactly one public CDP `Browser.crash` request over the browser-level
session obtained from the owned persistent context. The protocol describes a
browser-main-thread crash, distinct from graceful `Browser.close` or a GPU crash.
No PID is used to signal a process. Before dispatch, revalidate the canonical
profile sentinel, exact profile argument, browser PID/starttime and the owned
process group and session. Bind reported CDP processes and observed group/session
members to their identities using read-only `/proc` metadata.

A rejected CDP call alone is not evidence of a crash. Require closed pages,
browser disconnection, absence of the original and inventoried process identities,
and empty observed group/session membership before reopening. Recheck before
launching the same profile offline. Unsupported methods, unexpected protocol
errors, missing metadata, PID reuse, survivors and ambiguous termination fail
closed: retain the synthetic profile and do not qualify recovery. After dispatch
there is **no kill or close fallback** to make the first-process evidence pass.
No cgroup, sandbox, security or process-management setting is changed.

The second process must have a fresh identity and inert initial pages. It starts
offline before navigating to the same origin; require the installed SW response,
served index hash, actual maintenance barrier, offline state and failed uncached
probe. Compare storage with the original snapshot without reseeding, copying,
importing or refreshing TTL. Historical deletion of the future UNSENT row remains
an expected incompatibility counterexample, never permission to activate it.
The current reader must retain it. Both retain v1 content, journal and the separate
protection checkpoint. Gracefully close the recovery process and verify its
observed process inventory is absent before deleting the owned synthetic profile.

## Explicit limits

The inventory/group/session checks are conservative observations of a trusted,
pinned engine, **not absolute process containment**. They cannot prove exclusion
of an arbitrary descendant that escapes both group and session without appearing
in the inventory. They do not justify killing unobserved processes. Any observed
survivor, visibility error or identity ambiguity blocks reopen and deletion.
An isolated runner boundary would require separate evidence and authorization;
this increment does not configure one.

This is an injected browser-main-thread crash on Linux, not power loss, OS crash,
disk flush, filesystem durability, arbitrary-process containment or supported
physical-platform acceptance. It is not concurrent handover or authenticated
unknown-command recovery. Different historical/current profiles are independent
controls, not a migration. G1–G6 remain open and the existing-bicycle selector
remains inactive.

## Qualification status

Native execution is pending. No local browser launch bypasses the previously
reported environment restriction. New native cases being authored or collected
do not count as passes. Tests-first local controls exercise identity, lifecycle,
error ordering and fixture semantics without claiming native crash behavior.
The candidate needs independent source review and fresh source-bound CI after
specific publication authorization. Prior baseline results are not reused.

Primary design references: [CDP Browser protocol](https://chromedevtools.github.io/devtools-protocol/tot/Browser/),
[public browser CDP sessions](https://playwright.dev/docs/api/class-browser#browser-new-browser-cdp-session)
and [Linux process metadata](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html).
Pinned Playwright launch/exit behavior was inspected locally; a generic upstream
reference is not qualification of the actual native candidate.

Local candidate checks: **1,623 frontend tests passed**, **210 repository tests
passed**, **37 crash lifecycle/identity controls passed**, and **seven crash
fixture controls passed**. TypeScript, ESLint, prescribed formatting and diff
checks pass. The actual production PWA builds and both isolation checks pass,
including markers for the new crash helper. The historical App reproduces seven
hashed assets; the current committed archive is checked when sealing the source.
Seven native cases are collected (two reload, two graceful restart, two crash,
one engine diagnostic), **zero executed locally**. Full backend/aggregate and
native qualification are not claimed by this scoped local test increment.
