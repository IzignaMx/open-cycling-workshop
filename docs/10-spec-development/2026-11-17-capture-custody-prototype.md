# Inert draft custody prototype

Baseline main `ffa51bbe42c1108da2c198379c4f97eac9ef2508` follows PR110.
The coordinator reports CI43823790616 passed for that baseline; it is not this
candidate's qualification. Earlier authored pending checkpoints remain historical.

## Useful increment and boundary

The proposed [transition ADR](../02-technical-architecture/2026-11-17-capture-custody-transition.md)
separates preserving an unsent draft from granting authority to act on it. This
OFF-007/recovery prerequisite adds executable custody, rather than repeating App
reload/crash/isolation scenarios. It makes **no operational restore**, production
handover, origin decision, deployment or selector activation available.

Source inspection reuses actual kernel validation and Dexie readonly transactions.
It checks live synthetic admission, context/partition identity, capture writer,
checkpoint and exact v1 rows. It refuses any journal, delivery or operation-event
record, even applied history, and more than two total draft rows or foreign content.
This deliberately narrow empty-history prototype is not a migration tool for a
populated workshop. Unsupported, PROTECTED, UNAVAILABLE or stale state refuses.

A detached bounded bundle preserves full content, checkpoint provenance, portable
owner routing tuple and original absolute TTL. It excludes session bindings,
credentials, context grants and command payloads. The test-only staging database
contains only custody, never operational journal/capture stores. Identical transfer-ID
retry is idempotent; different bytes conflict. Writes and full readback verification
are atomic; nested transactions are refused so no outer abort can invalidate an
already acknowledged stage or expose uncommitted custody; quota/error/session-loss abort cannot acknowledge partial custody.

A process-local opaque witness permits coherent source reinspection. Differences
report source_changed; successful comparison says source_unchanged_at_check only.
The witness cannot survive process restart and is not durable ownership evidence.
The source can change immediately after that observation: every retained result
remains operationalUse forbidden. No automatic merge, source disposal or dispatch
exists. The source and target are separate transactions, not a distributed lock.

Custody readback refuses wrong owner, expiry, clock rollback or corruption without
returning payload. It does not silently delete expired copies or reset their TTL.
Only synthetic disposable databases are cleaned by tests. Real retention/logout,
authenticated export/import and user-visible recovery require a separate design;
no production user data may enter this prototype. Inputs are generated synthetic
objects, not a hardened arbitrary-upload parser or cryptographic attestation.

## Evidence and unresolved work

Tests exercise actual kernel/Dexie source inspection and fake IndexedDB staging:
exact multiline content/selection preservation, readonly transaction membership,
source refusal without writes, empty/history/foreign data, current admission and
scope failures, generation/revision/writer changes, atomic quota/readback abort,
ID collision and concurrent identical retry, database reopen, corruption and TTL.
Actual source autosave is injected before staging and before recheck; both detect
drift. A write immediately after successful recheck demonstrates why custody is
still inert. New uncertain journal work after staging refuses source verification
without removing the retained copy.

No native browser execution is claimed for this increment. Fake IndexedDB transaction
and close/reopen tests are not browser process restart, power-loss, disk durability
or real cross-origin transfer evidence. The prior native lifecycle suites remain
unchanged and distinct. Production isolation checks prohibit custody helper markers
in source and built App JavaScript.

G1–G6 remain open. Next substantive work requires choosing the transition contract:
finish old work at source or explicitly reconcile newer edits and command history;
then implement authenticated custody/retention and a separately qualified promotion
protocol. A temporary copy and point-in-time comparison do not solve exclusive
handover or exclude an old offline writer.

Local checks are recorded with the final candidate receipt; no hosted result or
production acceptance is inferred from source, collection or unit tests.

## Local qualification

The initial frontend runner passed **1,709 tests**, including **47 custody/source/
staging/coordinator controls**, with zero failed or skipped tests. Independent review
then reproduced an outer-transaction acknowledgement gap. Staging and custody reads
now reject nested transactions; both outer-abort regressions were observed RED and
then GREEN. These changes supersede the initial frontend receipt; final rerun is
recorded separately below. Repository contracts
passed **215 tests**. Production PWA build and both source/built-JavaScript isolation
checks passed. Scoped ESLint, Ruff, formatting and diff checks passed. Source/staging/
coordinator tests were observed RED before their missing modules were implemented.
This evidence is local and synthetic; hosted CI and independent review are recorded
separately against the sealed candidate rather than inferred from these counts.

Final corrected-source verification: **1,711 frontend tests passed**, zero failed or
skipped, including **49 custody controls**. The independent reviewer also ran all
49 controls successfully and accepted the nested-transaction correction. Repository
contracts passed **215 tests** after the documentation update. Production remains
unchanged; the PWA build and its two isolation checks passed. This is not native or
hosted qualification, nor acceptance of the proposed transition ADR.
