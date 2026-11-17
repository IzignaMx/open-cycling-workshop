# Native IndexedDB custody qualification

Baseline main is `7fa4e27f8281f67640800da80da8adc0cc37db9f` after PR111.
This increment qualifies a new boundary: PR111's inert custody implementation in
browser IndexedDB, rather than adding another historical App reload/crash scenario.
It is an OFF-007 recovery prerequisite; it is not pilot acceptance or a change to
the [proposed transition ADR](../02-technical-architecture/2026-11-17-capture-custody-transition.md).

## Exact implementation under test

The isolated browser build imports the same source snapshot, staging and coordinator
modules as the unit suite. Source hashing uses WebCrypto instead of Node crypto;
canonical input and SHA-256 output remain the same. Hashing happens before the
readonly transaction; live authority is checked again after the asynchronous work.
A regression test revokes synthetic admission while the digest is pending.
Production App, schema, runtime and write formats are unchanged.

The harness uses actual KernelDatabase, AccessKernel and Dexie with synthetic
context/baseline admission only. This is not the actual App or Service Worker, and
it is not authenticated handover. The Playwright driver explicitly transports a
detached bundle between two loopback origins in one disposable browser context.
There is no application export/import endpoint, credential bridge or promotion API.
Source witness objects remain in their originating page; they are not serialized.

## Evidence required from the native cases

- Preserve exact v1 draft content and original absolute TTL through source snapshot,
  destination staging and destination reload without reseeding. Check target custody
  has no operational stores. Retry the same transfer ID without duplicating rows.
- Edit the source from another same-origin tab during the protocol and observe
  source_changed rather than treating the old snapshot as current. Retain both the
  new source edit and the earlier inert custody copy. No exclusivity is inferred.
- Refuse altered package/owner/transfer-ID collisions. Prove both nested staging
  and reading reject an outer transaction before it can later abort, preserving
  the PR111 regression in native IndexedDB rather than relying only on fake IDB.
- Verify exact current checkout/source/lock/build provenance and all served asset
  hashes on both origins. A self-consistent foreign manifest is insufficient.
  Preserve traces, JSON results and build provenance as separate CI evidence.
  Provenance trusts the runner filesystem: source hashes describe working-tree
  bytes and asset hashes describe the local build. HEAD/tree labels alone do not
  prove those bytes belong to that commit. Hosted review must compare them to the
  exact candidate; this is not cryptographic release attestation.

The package carries synthetic private-content equivalents only. Cleanup operates
only on the owned synthetic database names and disposable context. No real data,
production filesystem, source records or operational journal are migrated or purged.
History/PROTECTED/unsupported refusal remains unchanged from PR111.

## Boundaries and status

**native execution pending** until hosted results are inspected. Build, test collection
and fake IndexedDB harness tests are not native browser evidence. Local browser launch
remains prohibited; this increment does not retry it or bypass the restriction.
Destination page reload is not a browser process restart, abrupt crash, physical
durability proof or offline App/SW installation. Test-driver transport is not a real
cross-origin permission or authentication mechanism. Synthetic authority and clock
inputs do not qualify server authorization, revocation or real retention/logout.

Even after passing, the copied bundle remains operationalUse forbidden. A successful
source check is a point-in-time observation, not a lock against future old-client
writes. G1–G6 remain open; the selector, richer format, production migration and
deployment remain off. Choosing source completion versus conflict-aware promotion,
real privacy/retention and a production artifact floor still requires the transition
contract and its separate implementation and qualification.

## Local qualification

The final frontend runner passed **1,736 tests**, zero failed/skipped. Focused
controls comprise **50 custody**, **19 provenance** and **5 harness** tests; the
independent reviewer reran all **74** successfully. Repository contracts passed
**217 tests**. Native spec typecheck and collection found **2 cases**, zero executed.
Production PWA build and both production-isolation checks passed; scoped lint,
formatting and diff checks passed. The isolated browser harness built successfully.

RED receipts retain asynchronous-digest admission revocation, missing provenance
implementation and unsafe asset path rejection before their fixes. The intermediate
manifest-tree-key mismatch/build rejection is preserved as superseded development
evidence, not candidate qualification. Source/manifest/build identities and final
local receipts are retained with the sealed candidate; hosted native results remain
pending. Independent functional review accepted the bounded synthetic scope.
