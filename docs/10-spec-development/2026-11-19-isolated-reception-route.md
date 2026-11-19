# Reception with an independently interrupted synthetic API route

Baseline: main `06dc8f8d96da2cf7292e843160125145a50019e9` (PR116).
Status: authored; native execution pending. No product changes.

## Decision and difference from existing evidence

This journey checks a complete inline bicycle plus dependent service order, not
only customer synchronization. Two independent browser contexts use the same
current App and synthetic server, with independent login and local storage. A uses
its own loopback fixture on port 5176; B uses the normal preview on 5173. Unlike
PR115 this is not source completion followed by new work in another origin. Unlike
PR116 it does not report reception timings. No physical LAN or absent Internet is
simulated or qualified, and no external destinations are blocked.

The test first confirms the shared synthetic customer through both clients. It
closes A's API barrier and waits for earlier forwarded requests to drain **before**
authoring the reception. A observes a rejected fetch while B still receives an
authenticated successful server response. The current App and SW remain served,
and browser `onLine` remains true. These signals alone do not prove absence of
server writes: monotonic proxy counters must show no new forwarding and B must
receive resource-specific absence responses for both new IDs before and after A
reloads. The original journal and bicycle dependency must survive reload.

Reopening A allows ordinary runtime reachability and synchronization. No manual
mutation replay, fabricated online event or changed user intention is introduced.
Both original operations must become applied and confirmed by server GET. B then
reads the same IDs, while its own journal remains empty. The bounded complete feed
must contain exactly the initial customer and the two expected new creations,
each version one. This detects observed duplication in this synthetic dataset,
not duplicate human intentions or all concurrency failures.

## Why this fixture needs an explicit transport failure

The historical upgrade fixture keeps its default HTTP 503 behavior. A received 503
is a reachable response, not a network error. Current session verification treats
such a refusal differently from transport unavailability; it cannot be used to
justify READY offline recovery. The current-route fixture explicitly selects
`socket-drop`: while closed it destroys only the socket for its accepted API
request, before any upstream dispatch. It does not cancel prior forwarded work,
change system network/firewall/TLS settings, cut static App/SW/control routes, or
change B. The same explicit close/drain/open protocol and monotonic evidence are
reused. Unknown fixture modes fail before a listener starts.

Unit controls distinguish default 503 from rejected transport, verify static and
API-like paths remain available, keep the other host available, and prove reopening
is refused while earlier upstream work remains active. Drain is an observation of
proxy connections, not a general proof of server transaction completion. Here the
new entity IDs do not exist until after the barrier has closed, and authenticated
server absence is independently checked. This preserves the lesson from PR114:
network errors by themselves do not prove an operation never reached the server.

## Evidence and limits

The native case retains its successful trace and a minimal synthetic receipt.
Native execution is pending, with no local browser launch. Any unexpected recovery
behavior fails the test and needs diagnosis; it is not a performance sample or a
reason to weaken session fencing. Node fixture tests do not qualify App recovery.
No real user data, operational migration, selector, format activation, deployment,
production origin/authentication approval, or legacy-client exclusion is added.
G1–G6 and physical LIBERTAD acceptance remain open.

The practical input for a future physical trial is the existing equipment/origin
sheet: identify the actual server and client devices, OS/browser versions, and
approved trusted origin/network path. Reuse the safe physical protocol and T1–T8
in `MANUAL-ACTIONS-CHECKLIST.md`; do not improvise certificates, installation or
security changes. Completing that sheet is not permission to run or deploy.

## Local authoring validation

- Socket-mode RED: the expected transport rejection fails under the former HTTP503 behavior.
- 23 fixture tests pass (20 historical controls and three current-route controls).
- Full frontend suite: 1,789 pass, zero failures/skips.
- Repository contracts: 223 pass.
- E2E TypeScript, scoped ESLint, production build and two production-isolation controls pass.
- Playwright collection finds the one new case. Collection is not native execution.
- No local native execution, physical timing, or LIBERTAD acceptance is claimed.
