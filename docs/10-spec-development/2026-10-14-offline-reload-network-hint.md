# Offline reload when the network hint is stale

Increment C correction, limited to the existing authenticated workshop slice.
The first PR38 browser trace shows offline reload issuing `/auth/me` and failing
before local readmission. A browser online hint is not proof of API reachability.

## Required invariant

For reload with a retained admission, validate its exact configured API realm,
principal and account scope before sending its bearer. Capture the complete
session snapshot through a read-only `/me` preflight. Only an unreachable-network
failure of that initial request may enter the existing offline-admission path.
No verification-generation mutation precedes that fallback. The unchanged kernel
must still verify owner CAS, full retained proof, incarnation, session binding,
monotone clock and the original lease. No lease is renewed by a failed request.

A successful `/me` continues normal expected-owner verification and authoritative
context acceptance. A reachable denial, non-success HTTP status, malformed
response or changed principal must fail closed and invalidate the old admission
through normal verification; it cannot become offline access. Non-success status
classification precedes body consumption, including an interrupted error body.
Later context/baseline failures cannot reuse the preflight admission. Login and
explicit reconnect remain server-authoritative. Automatic post-write scheduling
must not convert an unverified offline session into an implicit reconnect merely
because the browser's online hint remains true.

Tests cover the observed unreachable `/me` branch, unchanged pending history,
one owner advance, no lease extension, subsequent offline writes, error statuses
with interrupted bodies, malformed/foreign principal responses, stale owner,
clock/lease refusal, configured-realm/account mismatch and same-token/binding
session replacement during preflight. Browser/Compose qualification remains
required; emulator checks do not prove the hosted fix.

## Local evidence

The initial combined controller/transport regression run had 28 passing and six
failing tests: the observed stale-hint reload, four scope mismatches, and received
refusal status classification. The completed focused matrix passes 45 tests;
the full affected frontend core passes 507, with web/offline types and touched
lint/format/whitespace checks passing. The 507 total includes the separately
reviewed phase-only runtime diagnostic cases; it is not a new full repository
aggregate.

An independent external bridge using actual floor1 FastAPI routes, synthetic
SQLite, real context timestamps and emulated IndexedDB also reproduces HELD on
the previous compiled source and READY/offline on this candidate. It proves one
failed initial `/me`, one offline owner advance, retained valid proof, unchanged
binding/journal/delivery and both historical/pending customer projections. This
is local route/emulator evidence, not native Chromium, PostgreSQL or Docker
restore qualification. Exact hosted rerun and independent candidate review remain
required before merge.
