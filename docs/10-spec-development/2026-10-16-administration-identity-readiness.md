# Administration visual identity readiness · 2026-10-16

## Preserved failure and evidence boundary

This QA-only follow-up starts from local PR53 source `8780f85bbba8622628b3ff174e375aaef3891f20`
(published counterpart `67d56f6f2928686ed2d567ff4b2906a7684b69ba`). Direct browser artifact
`12051089473` records the administration theme test starting its first attempt
at `2026-10-16T14:16:15.253Z` and failing after 3393 ms. Its retry passed in 20362 ms.
The retry does not satisfy the retry-free gate or erase the failed attempt.

The preserved 1440 px and 834 px screenshots visibly show `OCWP`, as do the
320 px, zoom 1 diagnostic and error-context. The selected workshop suffix is
correct. This is not evidence of a narrow-width-only clipping defect. No artifact
is replaced by this change, and no authentication trace, video or automatic
failure screenshot is enabled.

The test waited for operational READY and a complete admitted baseline, then
sampled presentation text once. Selection clears the directory and branding;
READY does not await asynchronous shared-brand publication. Until that
publication, the shell can legitimately display its fallback. The backend's
version-zero brand response supplies the location name, but it must still pass
current admission and cache fences. A later writer can conservatively refuse a
cache publication, as documented in the connected-branding correction.

**The insufficient presentation wait is demonstrated; the original incident's
precise network/cache interleaving and eventual duration are unknown.** The
failed attempt ends while `OCWP` is still visible, approximately 2.7 seconds after
READY. The artifacts do not prove that it would have resolved within any proposed
timeout, nor that a production branding defect is fixed here.

## Narrow correction

Before any theme-loop screenshot, wait for exactly one workshop identity node
whose full text equals `Taller administración A`. The helper uses Playwright's
real `expect.poll` and the existing suite assertion timeout (10000 ms). It samples
`allTextContents` without waiting for a locator to appear; an absent node cannot
introduce a separate locator timeout. Array equality rejects missing and duplicate
nodes as well as a wrong name. No fixed sleep, timeout override, retry change,
production identity mutation or admission/cache relaxation is introduced.

The original text, word-fragment, geometry, mounted-node, draft, accessibility,
zoom and forced-colors assertions remain unchanged. Permanent wrong identity
still fails the test; this only moves readiness ahead of verified captures.

## Controlled local evidence

A Node-only harness executes the actual Playwright assertion against controlled
read-only identity observations, without a browser or application identity edit.
The immediate-snapshot precursor was observed RED: pending-to-correct rejected,
the negative control did not retry, and the integration hook was missing.
After correction, five checks pass:

- fallback observations followed by the exact name succeed after three reads;
- a fallback that never changes rejects, with its failure explicitly caught;
- absent identity rejects;
- duplicated identity rejects;
- the administration hook precedes the first theme loop and adds no helper budget.

The standalone Node runner uses Playwright's unchanged default assertion timeout
(5000 ms); the browser suite retains its existing 10000 ms configuration. These
are helper/control checks, not evidence of an executed browser journey. Fresh
exact-source direct and aggregate browser qualification, including the retry-free
gate, remains required. Independent source/docs review and a separate five-case
helper run passed for the initial candidate tree; final package/body review and
hosted qualification remain pending before publication claims.

Additional local checks: all 917 frontend core tests passed with zero failures
or skips on supported Node 24.19.0; 22 repository contracts, touched
ESLint/Prettier, normal web TypeScript and helper checkJs passed. Initial aggregate
attempts exposed stale workspace links and a missing local fake-indexeddb link;
correcting only local dependency links to existing pinned packages enabled the
complete passing run. No dependency manifests or lockfiles changed. A standalone strict typecheck of the
entire administration spec remains blocked by the existing `toHaveAttribute`
argument at baseline line 1011 (line 1013 after this patch): `string | undefined`
is not accepted. The identical error was reproduced from the baseline source
using the same dependencies. It is not changed or reported as passing here.
