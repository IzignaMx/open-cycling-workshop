# Source-work diagnostic before a transition decision

Baseline: PR112 main `ddb6bd17700f9c8e3eef76463bf32a85bc0d2eed`.
Status: test-only prototype, not a production transition decision or pilot acceptance.

## Recommendation and finite path

Prefer completing prior work at its original source over automatically promoting an
inert copy. This recommendation does not retire an offline client, prevent later edits,
or choose a production origin. The proposed custody ADR remains proposed.

1. Observe existing local work coherently and identify its existing source workflow.
   This increment implements that diagnostic contract only.
2. Decide the protected entry point, coexistence contract, authentication and privacy
   policy in the transition ADR. No domain or deployment is selected here.
3. Rehearse resolving old work at source and starting genuinely new work at destination,
   with server identity/dataset, duplicate prevention and recovery qualified separately.
4. Complete physical platform, backup/restore and pilot acceptance gates.

## Observation, not readiness

`tools/source-transition/diagnostic.mjs` reads KernelDatabase in one readonly
transaction. It verifies the supplied synthetic current-authority callback, exact
stored ticket/admission, scope, lease and baseline. The callback is trusted test
input, not authentication. No production App integration or authority is added.
It does not call kernel session inspection, which uses a read-write transaction.

Limits are 32 checkpoints, 64 content rows, 128 journal rows, 128 delivery rows and
512 event rows. Each read requests at most limit + 1 rows; overflow refuses the
whole observation instead of reporting truncated absence. These are row bounds,
not a guarantee against arbitrarily large/corrupt individual IndexedDB values.
This is not a 100k-store capacity qualification or a paginated operational inspector.
Foreign scope, malformed correspondence, orphan records and uncertain reads refuse.
Any valid applied history is retained and counted separately, never a purge request.

The detached receipt contains only a timestamp, coverage label, aggregate counts,
action codes and fixed `activation: not_assessed`, `migration: forbidden`. It has no
customer data, operation IDs, scope identities, grants, session binding or payload.
The caller must not present an empty action list as global readiness. It covers one
bounded local database at a point in time, not other devices, profiles or offline tabs.
An opaque process-local witness can recheck exact inspected bytes. A changed or
unavailable recheck invalidates that observation; even unchanged_at_check is not a
lock, durable receipt, transferable authority or promise against the next write.

## Suggested existing workflows

| Observation                                     | Suggested action only                                    |
| ----------------------------------------------- | -------------------------------------------------------- |
| Supported, unexpired UNSENT capture             | Finish/review the existing capture at source             |
| PROTECTED metadata                              | Check its existing capture receipt; do not submit again  |
| Inflight or awaiting confirmation               | Check the unknown outcome through source sync/recovery   |
| Other unresolved delivery state                 | Review source sync, conflict or recovery status          |
| Applied result with consistent journal/delivery | Retain applied history                                   |
| Unsupported payload                             | Use compatible source recovery; never reinterpret it     |
| Expired or unavailable capture                  | Review source recovery; do not infer permission to purge |

No suggestion executes a send, retry, cancellation, discard, purge or migration.
No operation ID is replaced, no TTL restarted, and no payload restored/promoted.
Existing guards and user approvals still govern any later source action.

## Evidence and limits

Tests use disposable fake IndexedDB databases and the real kernel to generate
ordinary draft, PROTECTED, pending and applied-history states. Corruption and other
held states are explicit synthetic negative fixtures. Tests compare complete database
bytes before/after observations, cover scope and missing records, capacity refusal,
revocation during async hashing, stale witnesses and edits after the observation.
No native browser, physical device, real user data or production transition is used.
G1–G6, selector activation, production artifact floor and physical acceptance remain open.

Recheck also compares the derived diagnosis, not only stored bytes: original TTL
can expire between observations without a write. A RED regression caught an
incorrect unchanged_at_check in that case; the corrected witness includes counts
and actions, while the observation timestamp itself does not create false drift.

Local candidate qualification: **1,771 frontend tests**, **218 repository contracts**
and **34 focused diagnostic controls** passed. Production PWA build, both
production-isolation checks, scoped ESLint/Ruff, formatting and diff checks passed.
The earlier 1,770-test run predates the expiry correction and is superseded. Local
pnpm/link-resolution build failures are retained separately from the successful
build. No native or physical execution is claimed for this diagnostic increment.
