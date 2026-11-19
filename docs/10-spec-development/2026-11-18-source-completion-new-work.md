# Finish an existing source capture, then author genuinely new work

Baseline: main `e1332790885ff5b2941058d08e8dfb624403d29a` (PR114).
Status: hosted native journey qualified on PR115/main; physical acceptance remains open.

## Finite recommendation

Prefer completing existing work through its original supported source workflow,
confirming its authoritative outcome, and using independently authenticated new
entry for genuinely new work. Do not promote an inert copy or relabel an unresolved
command as new work. This is a recommendation to evaluate, not an accepted transition
ADR, protected production entry point or operational handover authorization.

This increment rehearses that finite route using the current production App build
and actual server authentication, baseline and mutation endpoints, with disposable
synthetic identities/data. It does not repeat the readonly diagnostic classifier or
invent a second implementation. A and B are two loopback ports in the same browser
context, not production domains. Both preview servers serve the same current dist;
the observed entry module and service-worker bytes must match. Historical artifacts,
legacy-client exclusion and update/rollback are not part of this journey.

## Causal proof

1. Create a private synthetic location/account, author a customer at source A and
   require its durable applied acknowledgement and authoritative cache version.
2. Fill an order without an inline bicycle. Require an acknowledged UNSENT capture,
   original 24-hour TTL and no order command. Reload A, require recovered fields,
   identical payload, checkpoint identity/revision and original expiry, and unchanged
   journal. Ignore only `observedAt`, which the real load advances legitimately.
3. Submit the recovered capture through the real UI. Require durable applied result,
   authoritative delta and a server GET matching the exact ID/payload/version. Retain
   the journal. A clean projection/default selection may remain UNSENT by contract;
   completion is not a purge or a false claim that every capture row becomes EMPTY.
4. Open B in the same context and log in independently via the real server. Require
   same organization/user, location and dataset, distinct API realms, and complete baseline containing A's server
   order, but empty local journal/delivery/events and no capture contents. Check no
   source checkpoint/generation was copied. No credentials, storage or witnesses
   are transferred by the test. B starts without a sessionStorage token; its observed
   successful login must issue the distinct token stored in B while A retains its
   token. Actual server auth/context responses must match each kernel's identity,
   location, dataset, epoch and policy. Cookies share the loopback host across ports;
   this does not claim cookie isolation or a production authentication bridge.
5. Author a deliberately different order through B's UI. Require distinct entity and
   mutation IDs, applied result and matching server GET. A reload must preserve its
   journal, applied delivery and stable capture data. Server feed for the private
   location must be complete (`has_more: false`) with exactly the two order creations,
   each at version 1; no truncation is interpreted as absence of duplicates.

The case retains a successful Playwright trace as well as a minimal JSON receipt
with synthetic IDs, counts and fixed scope labels. No authentication token, private
payload or full database snapshot is copied into that receipt. Trace is disposable
synthetic test evidence, not a user-data export. Local source guardrail tests check
ordering/configuration only; they cannot qualify browser behavior.

## Limits and remaining decisions

This is a connected completion path for supported UNSENT work. PROTECTED, unknown,
conflicted, expired or unsupported work must stay in existing source recovery until
resolved; this case does not qualify those paths or recreate them in B. Assertions
stop the scenario before destination authoring unless source completion is confirmed.
It cannot prevent a person manually entering the same business intention again.
Distinct synthetic IDs and content prove only this observed journey, not semantic
or global duplicate detection.

A remains usable and is not retired. There is no lock, exclusive writer transfer,
migration, automatic retry, source purge or prevention of future source edits. Sync
may legitimately change cache/cursor/authority metadata; whole-database equality is
not asserted. No selector, new format, product runtime or security configuration is
changed. G1–G6 remain open. The proposed transition ADR still requires accepted
protected entry/authentication/coexistence/privacy/recovery decisions, followed by
physical backup/restore and LIBERTAD pilot acceptance. This evidence is useful for
choosing the completion-at-source route, not permission to deploy it.

## Local authoring qualification

Frontend **1,777 tests passed**; repository **222 contracts passed**, including three
new authoring guardrails (the first two observed RED and then GREEN). The native spec is in
the regular TypeScript compilation path. Scoped lint/format/diff checks, production
PWA build and both production-isolation checks passed. Official collection found
**one new direct case, zero locally executed**. No native/physical claim follows
from these checks; successful hosted trace and receipt require separate review.

## Hosted qualification reconciliation (2026-11-19)

PR115 merged as `95813a35123884e2f310b6c696c41361e3570e54`, exact tree
`58fb6ad5535e8df2006f7ad0ff45b09025ff5e0a`. Main
[CI 44254219936](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/44254219936)
passed. The coordinator recorded independent review of the successful native trace
and receipt, including source-history preservation and the complete private server
feed. See [PR115](https://github.com/IzignaMx/open-cycling-workshop/pull/115).
This supersedes the pending hosted status, not the historical local authoring counts
above. It does not qualify the later reception measurement candidate, physical
hardware, migration, exclusivity, production authentication decisions or G1–G6.
