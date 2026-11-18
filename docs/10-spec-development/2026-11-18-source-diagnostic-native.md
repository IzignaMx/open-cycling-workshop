# Native IndexedDB source-work diagnostic rehearsal

Baseline: PR113 main `cc1a37b844155e7fde958d23110d0efe01c04299`.
Status: implemented; **native execution pending**. This is not physical LIBERTAD
pilot acceptance or a production transition decision.

## One finite additional case, no parallel infrastructure

Extend the existing custody harness/spec/config/CI artifact path with one case.
The browser imports the exact `tools/source-transition/diagnostic.mjs` module used
by PR113, not a replicated classifier. The existing two custody cases remain.
Provenance on both served origins now includes the diagnostic source directory;
negative controls reject mismatched or missing diagnostic hashes. Runner filesystem
trust and independent comparison against the exact commit remain required.

The new case seeds disposable synthetic drafts, then uses actual AccessKernel APIs
for local command creation, dispatch claiming and application of an explicitly
fabricated server response. There is no fetch, real server acknowledgement, sync
service or authentication claim in these fixture helpers. It observes pending,
inflight/unknown and applied-history states, retaining the immutable journal.
Every successful diagnostic observation compares full database bytes before/after.
Receipts omit payloads and identity fields and retain migration: forbidden and
activation: not_assessed. They never execute suggested actions.

Observation witnesses remain in the originating page. The driver receives only an
opaque handle and the minimal receipt, never the witness itself. Release/cleanup
invalidates the page's handles; cross-database handles refuse. This is not a durable
receipt or authorization mechanism. Disposable fixture maps are not a production
retention policy.

## Clock and authority causality

Draft TTL is 24 hours while the fixture's admitted lease remains one hour. The
fixture must not stretch authorization to make a TTL assertion pass. It explicitly
advances its monotonic injected clock near the original TTL and renews admission
through beginVerification(expectedOwner)/acceptVerifiedContext/rememberSession.
Only then does it take a fresh observation, cross the original expiry and require
changed diagnosis with unchanged stored bytes. This proves the branch under an
injected clock, not wall-clock waiting, offline survival, physical durability or
clock synchronization. A preliminary attempt to enlarge the synthetic lease was
rejected by the existing maximum-lease validator and was removed, not bypassed.

Finally a second same-origin page verifies its own kernel instance. The original
page's old ticket/witness must be refused for authority, and the new page observes
the retained applied history and expired drafts. Verification is a fixture action
separate from readonly observation and legitimately changes authority metadata.
Neither unavailable nor unchanged observations permit migration or activation.

## Remaining gates

No production source, schema, diagnostic semantics, server, workflow, selector or
format changes. No new browser launcher, deployment or production domain. No real
records, command submission, handover or purge. Native local launch remains
prohibited; authored collection/build is not execution. This test does not complete
G1–G6, the proposed transition ADR, physical backup/restore or pilot acceptance.
The finite next decisions remain protected entry/coexistence/authentication/privacy,
then source completion versus genuinely new destination work and physical acceptance.

## Local qualification

The frontend suite passed **1,775 tests**; repository contracts passed **219**.
Focused controls passed **63** (34 diagnostic, 21 provenance, 8 harness). Native
TypeScript, isolated harness build and collection passed: **3 collected, 0 executed**
locally, comprising two existing custody cases and one new diagnostic case.
Production PWA build, both isolation checks, scoped lint/format and diff checks
passed. The new native case requires hosted execution and independent artifact
review; these local counts do not qualify it as passing in Chromium.

## PR114 direct-suite precondition correction

Hosted run 44225432628 failed the existing direct legacy-upgrade case: the global
absence assertion found the synthetic offline customer twice (139 other direct
cases passed, no retry). The trace confirms the current bundle and READY runtime,
not a legacy document: its server baseline page already contained that customer.
The legacy database preservation and empty new operation journal assertions passed.
Two historical mutation requests were recorded as offline network failures; that
observation alone did not prove absence of a server commit. The precise transport
cause remains unproven. Runner logs add no request-level attribution. No product
isolation defect or Chromium/SW root cause is claimed.

The test-only loopback proxy now has an explicit API isolation interval in addition
to browser offline emulation. Before authoring, it closes API forwarding and drains
already forwarded requests, records monotonic forwarding counters, and uses a
readonly CLI probe to require the fixed synthetic customer absent from the dedicated
floor-zero tenant. After both offline reloads it requires the same forwarding count,
zero active requests, still-closed isolation and server absence again. Only then may
it activate the floor and reopen the proxy. It neither aborts prior upstream work
nor deletes server data to manufacture absence. A contaminated fixture fails early.
The minimal before/after counters and absence receipt are attached to native results.

This strengthens the journey's precondition: it is browser-offline **plus explicit
synthetic proxy isolation**, not proof that browser emulation alone isolates all
transport. The exact historical App/SW, offline toggles, preserved DB/journal checks,
global text absence assertions and timeouts remain unchanged. The barrier is not
production networking/security configuration, migration authority or old-client
exclusion. Corrected native execution remains pending; previous failure is retained.

Correction qualification: frontend **1,777 pass**, repository **219 pass**, proxy
**20 pass** (two new controls first failed), Python fixture **14 pass** (six new
controls first failed). Scoped lint/format and official direct-case collection
pass. An ad-hoc standalone TypeScript configuration was not a qualification: it
lacks Node declarations and exposes existing unchecked optional database rows;
its unsuccessful diagnostic is retained separately. No local native replay was
performed. Corrected hosted direct execution is still required.
