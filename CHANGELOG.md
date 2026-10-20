# Changelog

## Fixed full-Python PostgreSQL budget and scanner policy · 2026-10-20

- Preserve failed CI 39153233846: 4,430 collected, 1,371 passed, six skipped,
  one PostgreSQL `DiskFull` failure and 3,052 unreached cases. This is not a
  completed qualification or a product-capacity measurement.
- Set only the full-Python PostgreSQL data tmpfs to 512 MiB and memory to
  1 GiB. Match creation, Docker inspection, cgroup observation and receipt
  policy. Preserve one CPU per container, zero swap, the 512-MiB worker,
  900-second Python deadline, fixed inode limits and mandatory cleanup.
  Finite microfixture budgets and both large synthetic fixtures are unchanged.
- Add a conjunctive exact rule/path/value exception for the public JSON-size
  documentation phrase flagged by `generic-api-key`, with actual-scanner
  canaries for the allowed phrase, a changed value and a different path.
  This does not exempt the file or disable default rules.
- Local runner/receipt checks: 258 passed, including eight new budget cases;
  five targeted cases first failed on the old budget. Also passed 52 scanner
  policy/security-wrapper tests with native Gitleaks 8.30.1, including all ten
  actual-scanner canaries and each exception's negative mutations. Hosted
  complete-suite and full-history security evidence remains pending.
  No merge, deployment or quote API/UI activation is included.

## Full-Python synthetic repository invocation · 2026-10-18

- Preserve [run 39151218879](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39151218879), published head `db5cc27a73d1c8567d1c77c5e57bd0ec360b0e55`, tested merge `418de1e9f2e427dbdd9baccf344b59b988cc9a56`, tree `a4025706a4cfded68b6d9cbb8f7a5ee061d64db4`. Actual pytest collected 4,427 cases without collection errors or deselections and reported 948 passed, five skipped and one failed, leaving 3,473 unreached. The real historical codec/cutover fixture, all five source-loader cases and three required database/branding restores passed; three required quote restores were unreached. The repository publication test then observed Bash exit 1, with its captured stdout/stderr absent from the complete 2,966-byte short trace. No exact failing shell command is retrospectively asserted. Final result/resource counters are absent; both manifest-owned cleanups verified absence, while builder cleanup remains unassessed.
- Run the unchanged release script from the test's existing synthetic source repository. The script calls `git bundle verify` before clone/cd; Git requires a current repository, including for a self-contained bundle. Its earlier test call inherited archive-only `/app`. The earlier source audit identified temporary Git objects but missed this inherited-directory prerequisite. The release helper's actual limitation is now explicit: invoke it from an existing Git repository; standalone invocation outside a repository is not supported by the current script. Production script bytes, local backup/ref/tree verification assertions and all real synthetic Git operations remain unchanged.
- Add bounded failure rendering only to this test module's public synthetic subprocess helper: preserve the same exception and return code, retaining at most 2,048 bytes of each captured-text stream re-encoded as UTF-8, with availability, total-byte counts, omitted-prefix offsets and truncation flags. These are not original raw subprocess byte counts; escaped JSON can be larger than the retained UTF-8 bytes. Three focused mock cases are prepared but unexecuted. Other shell consumers have no demonstrated equivalent missing Git-directory prerequisite, so no speculative edits are included. Workflows, resources, deadlines, skip/restore obligations and next-attempt review requirements are unchanged.

## Full-Python immutable legacy codec fixture · 2026-10-18

- Preserve [run 39149558971](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39149558971), published head `68d9c50184fd4f9ecd56b2137f14d66627481f34`, tested synthetic merge `7e66adad82cfdef24a2f9b1c34c2e75ad9c9bab3`, tree `7997293576a2e65c5a7cd8a013b775122d7f10d9`. Image preparation, cancellation canary and reached scratch checks passed. Actual pytest collected 4,422 cases without collection errors or deselections, then stopped with 180 passed, five skipped and one failed. The legacy fixture's pinned `git show` returned 128; its own stderr is unavailable. The other 4,236 cases, including all six mandatory restores, were unreached. No final result or final resource counters were retained; both manifest-owned cleanup checks verified absence, and builder cleanup remains unassessed.
- The source-only image is built from `git archive HEAD` and contains no historical Git object database. Package the exact 4,549-byte pre-cutover security source as an inert fixture instead. Independently verify commit `714342c60f4163c7b4c1ebec8433995dccbeea01`, tree `fbf5e5678188a97b8b9709e6f91cb6b250e20c9f`, path `services/platform/src/cycling_workshop/identity/security.py`, blob `0a13a1ac154f0b982589dfa09c470cf4aa61c4e0` and SHA-256 `95613b4278c0a966ecdd68445c8d5197e5d874f1678a35f8be930720811b87c6`. Runtime reads at most 4,550 bytes and requires the exact length and digest before the unchanged historical codec execution. This preserves the oracle without copying Git configuration, credentials, hooks or current implementation code. The demonstrated missing prerequisite does not recover the absent historical fatal message.
- Prepare five focused source-loading cases, including absent, truncated, modified and oversized fixture refusals, in the existing browser-fixture test module. They are unexecuted; its real cutover/session assertions remain unchanged. No workflow, dependency, skip, restore requirement or resource/output/deadline budget changes. Exact review and terminal current-run review precede any next attempt; complete integration, recovery reopening and activation remain pending.

## Full-Python fixed scratch-path observation · 2026-10-18

- Preserve [run 39147495876](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39147495876), head `172556621f430b3c8dcd73a5efb24a197b6187d2`, synthetic merge `1541412b95f2b657c2ada3a8a44ec89b49b8d658`, tree `17547cb85de4e033412b002bc8c77c0dcfd7787c`. Image preparation and the cancellation canary passed. The database scratch stage failed with `scratch_readback`; no business/pytest launch, collection or result occurred. Both manifest-owned cleanup checks verified absence; builder cleanup remains unassessed.
- Verify the exact recorded PostgreSQL image's official config and two digest-bound layer metadata sets: Debian `var/run` links to `/run`, and the socket directory is `run/postgresql`. The existing requested-path-only mountinfo lookup excludes that canonical destination. Historical raw rows are unavailable, so this demonstrated source incompatibility is consistent with the retained failure without proving its sole underlying cause.
- Keep the requested tmpfs paths, sizes and options unchanged. Require each existing realpath to equal its fixed expected canonical destination; only `/var/run/postgresql` maps to `/run/postgresql`, and every other path must resolve to itself. Match only those fixed kernel mountpoints and retain all type, allocation, ownership, permissions and mount-flag checks. Retain the first failed fixed path/check and bounded expected/observed scalars or free-space interval in the existing diagnostic. Malformed or unbounded observations are omitted; arbitrary paths, flags and raw rows are never echoed. Exact ownership-string comparisons and refusal ordering remain unchanged.
- Prepare eight additional mocked refusal cases in the existing scratch test and update its database fixture to the verified path representation. These and the earlier diagnostic cases remain unexecuted. All resource/time/output bounds, the 58 intentional skip identities and six required restore cases remain unchanged; exact review and terminal current-run review precede the next attempt.

## Full-Python containment observation correction · 2026-10-18

- Preserve [run 39145603647](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39145603647), head `e98ba57e106849fd4830fc955e7c7139663a691f`, synthetic merge `2a906c7fc276639f422b5f7b4ad4dd3384e19d5e`, tree `4059c1bd6d7bf6e23438785622c3258997bbd342`. Full-image preparation passed, then containment setup failed before a completed canary or business launch. The source-bound receipt retains `containment_failed`, null collection/result and zero database/worker samples; both manifest-owned cleanup checks verified absence. Its first failing assertion is unknown because specific preflight codes were discarded; no workload duration or test result is inferred.
- Correct a separately source-demonstrated Docker observation defect. The advertised runner uses Docker 28.0.4: its CLI stores `--tmpfs` in `HostConfig.Tmpfs`, while Moby's top-level `Mounts` comes from a separate collection. Require exact configured tmpfs options and an empty top-level mount list, rejecting alternate mounts. Keep pre-start identity/resource checks and all post-start kernel scratch/allocation/ownership/flag enforcement. Moving inspection after start is unnecessary. The historical first failure is not retrospectively assigned to this defect.
- Retain fixed preflight stage, role, closed failure code and failed-field identifier in the existing uploaded diagnostic JSON, below 16 KiB. It is unqualified evidence, never a receipt; raw configuration, arguments, environment and exception payloads are excluded. Later cleanup cannot overwrite the diagnostic's first refusal. All deadlines, resources, source checks and record/output budgets remain unchanged.
- Update the existing mocked Docker fixture to the real representation and prepare seven additional focused cases. They are unexecuted. Exact review and terminal current-run review precede any next attempt; full Python qualification, integration, reopening and activation remain pending.

## Full-Python executable entry and clean verifier workspace · 2026-10-18

- Preserve [the third preparation failure, run 39143857377](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39143857377), from head `7c436d9d94ff1b63e4eb78f39a8443426756f428`, synthetic merge `af4706a111b5a79524711e2e322d6037a1db5e3f`, tree `352ed2fab06747bad77cc79328401e3e5d5779ba`. The client returned 1 after the pnpm assertion failed with `Permission denied` (inner shell exit 127). The 39,855-byte spool stayed below 1 MiB; the retained 16,384-byte tail explicitly omitted 23,471 prefix bytes. The retained PG package/client and Node link/version checks passed; Playwright-package validation and pytest were not reached. Client reap is recorded; missing ownership remains unqualified and builder cleanup is not assessed.
- Change only the final-image pnpm symlink target to the official pinned 11.17.0 package's executable `bin/pnpm.mjs` (0755). The compatibility `pnpm.cjs` exists but is 0644; registry integrity, package entry and modes were independently checked as data. Keep the version assertion, pins, trust and all preparation/runtime budgets. The first two opaque failures do not retrospectively establish this same cause.
- Preserve [run 39141875819](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39141875819): the direct browser collection passed 80/80; the final verifier retained 24 passing checks and three Python/PG rejections with `identity_dirty`. Successful real branding uploads plus exact source identify a runtime writer beneath unignored checkout `var/branding-assets`; no porcelain listing survived to prove that it was the sole dirty path. Prepare a fixed early CI verify step exporting a private runner-temp asset path through `GITHUB_ENV`, with production defaults unchanged. Retain up to 4 KiB of path/status text on `identity_dirty`, with explicit byte counts/truncation and the existing rejection intact; no file contents or environment values are read. The original 16-KiB Git query cap still fails closed.
- Three new mocked diagnostic cases are prepared but unexecuted. Exact source review and terminal current-run review precede any next attempt. No complete full-Python receipt, final integration, capacity, reopening or activation is qualified.

## Full-Python build output localization · 2026-10-18

- Preserve both failed image-preparation attempts. In [run 39141875819](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39141875819), PR head `f525d4f07973926680c0f7564497886db7029eaf` ran as merge `dfb186e0c50e756262990895b54272bf2651475a`, tree `2a0d9179c8ad4612738329393872287f5ac9c9f6`. The reaped build client returned 1 and retained all 5,041 output bytes. Quiet Docker output identifies only the combined installation/version/link RUN; the failing subcommand and underlying cause remain unknown. Pytest was skipped. Independent cleanup truthfully recorded missing ownership, without certifying resource absence or builder cleanup.
- Prepare plain build progress and nine fixed labeled RUN phases without changing package trust, exact pins or version/link assertions. Only this fixed image-build client receives a 1-MiB spool instead of 16 KiB; its artifact retains the final 16 KiB after bounded reap, with observed spool bytes, retained bytes, dropped-prefix count, retention truncation and spool saturation recorded separately. Reaching the 1-MiB ceiling still fails; truncating only the retained tail does not change the actual command result. A saturated spool cannot establish total attempted output. Other controls retain 16 KiB, and worker limits, deadlines, the 1-MiB workload spool, 4-MiB proof records, 58 skip identities and six required restores are unchanged.
- New mocked cases are prepared but unexecuted. The earlier signed PostgreSQL restore recipe and the presence of both pnpm compatibility entries do not identify this build failure. No dependency fix or passing full-suite claim is made. The next attempt remains subject to exact technical review; no automatic retry or further output-budget widening is introduced.

## Full-Python preparation diagnostics · 2026-10-18

- Preserve the first [PR 58](https://github.com/IzignaMx/open-cycling-workshop/pull/58) attempt, [run 39140389383](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39140389383), on synthetic merge `6b166504dde92aa5fa42f85eef687fc97b2306eb` (tree `dd30aeb9530fb41f7e11aab5cde3b7859ef5dc13`). The first image-build invocation failed before PostgreSQL image pull or pytest; its output and actual child return code were not retained, so the underlying build cause remains unknown. The finalizer exited unsuccessfully without an independent cleanup record, and no full-Python artifact was uploaded.
- Prepare fixed-stage, 16-KiB preparation diagnostics and a separate independent cleanup observation, including missing-image/receipt paths. Missing ownership does not prove resource absence; client reap does not prove builder cleanup. Neither diagnostic can substitute for a passing full-Python receipt. Resource limits, deadlines, required restores and the exact skip ledger are unchanged. New mocked regressions are prepared but unrun.
- Preserve the same attempt's separate verification failure: Prettier identified exactly the bounded-effects ADR and integration-checks page. Apply the complete canonical two-file output from locked Prettier 3.9.6 using inert copies under the bounded developer-tool check. The main browser installation/journeys were skipped; the always-run verifier later attempted secondary fixtures without Chromium, reporting 80 unexpected tests and 159 failed attempts without assertion passes. Its aggregate retained 21 passed checks, five failed and one blocked; missing full-Python evidence failed closed without fallback pytest. Full integration remains pending.

## Clean quote service integration preparation · 2026-10-18

- Preserve [run 39091798151](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39091798151): 214 helper/verifier/guard cases and the repository command passed; Ruff failed and four later commands were unrun. Preserve [run 39092755007](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39092755007): repository and Ruff passed, the formatter output hit its 16,384-byte ceiling, and three later commands were unrun.
- Verify all six static commands on `f550cde9e7675f38e9523ad9998e4e04ea58d0a8` in [run 39093315481](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39093315481): zero failures, errors, skips or unrun commands; workload 10.852200477 seconds, final pre-termination peak 275,406,848 bytes, and both cleanup proofs independently verified.
- Reconcile the four reviewed canonical helper/verifier/test files into the clean source. Preserve product, migrations, functional tests and locks; retain experiment source and evidence in their published history rather than shipping the qualification controls. Earlier runtime results remain tied to their actual source.
- Pass the bounded locked Prettier 3.9.6 check for ordinary CI YAML and the three clean status documents. Set `persist-credentials: false` on the CI verification checkout so checkout authentication is not retained in the workspace used by existing recovery clients. Full-image preparation and final clean-tree/runtime qualification remain pending; the complete suite retains exactly 58 intentional skips, six restore cases and both ordinary larger specimens. Capacity, recovery reopening and activation remain unqualified.

## Quote oracle functional evidence and static formatting · 2026-10-18

- Verify all 66 corrected functional cases in run 39082181517. Six mocks, repository and lint also passed; formatter failed with 15 complete layout hunks in three auxiliary files, leaving types and both contracts unrun.
- Preserve that result and prepare only the retained format changes plus the existing 12-check mock/static workload under unchanged limits. Product and functional test behavior remain unchanged.
- Verify the 12-check closure in run 39082876503: all checks passed in 14.580 seconds, with exact source identity and cleanup independently verified. Full integration remains pending.
- [Evidence and closure](docs/10-spec-development/2026-10-18-quote-oracle-format-closure.md).

## Quote-only oracle adapter correction · 2026-10-18

- Preserve the existing regression run 39080692255: 259 cases in complete passing groups, including 39 PostgreSQL cases; four failed groups and all cleanup evidence retained.
- Correct only three stale test-callable boundaries and three reported SIM300 comparisons. Frozen oracles and product behavior remain unchanged.
- Prepare the same three affected groups plus six mocks/six static commands, 78 checks under unchanged per-group limits. [Evidence and scope](docs/10-spec-development/2026-10-18-quote-oracle-adapter-correction.md).

## Existing quote integration regression preparation · 2026-10-17

- Historical preparation: selected repository/oracle, schema, sync/outbox and cutover regressions comprised 325 functional cases plus six existing mocks and six static commands in 23 bounded groups. Execution was pending at that checkpoint; the 2026-10-18 entry records its result.
- Correct the obsolete unsupported cutover revision specimen from 0013 to 0014; the production supported revisions and positive matrix remain unchanged. No observed failing-before result is claimed.
- [Selection, evidence boundaries and pending integration gate](docs/10-spec-development/2026-10-17-quote-existing-integration-checks.md).

## Quote semantic static closure · 2026-10-17

- Verify all six static commands on 03e11cd8 in run 39078898414, with independent source/resource/cleanup review. Workload 14.408 seconds under the unchanged 20-second cap.
- Retain the separately verified 40 PostgreSQL cases and six mocks plus both failed static runs. Broader existing integration regressions remain pending.

## Quote semantic formatting correction · 2026-10-17

- Preserve run 39078500578: repository and Ruff passed; formatter requested one exact line join, with 47 other files formatted and types/contracts unrun.
- Apply only the complete retained hunk and prepare the existing static-six scope under unchanged limits; verification remains pending.

## Quote finite service semantics evidence · 2026-10-17

- Verify 40 actual PostgreSQL cases and six selection mocks in run 39077801165, including complete decisions/replay, reached-write rollback, synthetic commit ambiguity, payload checks and small observed-lock races. Independent source/identity/resource/cleanup review passed.
- Preserve the overall failed result: repository passed, Ruff found one import-order issue, and four later static commands were unrun. Prepare only the import correction and static-six verification under unchanged limits.

## Quote semantic closure preparation · 2026-10-17

- Prepare 40 finite service decision, retained-payload, reached-write atomicity and small PostgreSQL race cases with reviewed designs and unchanged resource limits. Product and schema behavior remain unchanged.
- Exact implementation review is complete; collection and execution remain pending. [Scope and remaining gates](docs/10-spec-development/2026-10-17-quote-semantic-closure.md).

## Quote loader static closure · 2026-10-17

- Verify all six static commands on 4b0a19b6 in run 39076298550, with independent source, resource and cleanup review. Workload 13.499 seconds under the unchanged 20-second cap.
- Preserve both preceding failed static runs and the separately verified 32 PostgreSQL cases. Broader service integration and activation remain pending.

## Quote selection layout correction · 2026-10-17

- Preserve run 39075919485: repository and Ruff passed, then formatter requested one exact continuation-line join; types and both contracts were unrun. Apply that retained line only and prepare the existing static-six scope under unchanged limits.

## Quote PostgreSQL loader/writer evidence · 2026-10-17

- Run 39075248467 passed all 32 real PostgreSQL cases and six selection mocks. The repository check passed; Ruff failed four new SIM300 comparisons and four later static commands were unrun.
- Preserve that partial result, correct only the reported comparisons and prepare a static-six-only verification under unchanged limits. Product and PostgreSQL test bodies remain unchanged.

## Quote candidate static closure and PostgreSQL coverage · 2026-10-17

- Verify all six static commands on cb2d8d48 in run 39074239970: repository, Ruff, format, strict production types, OpenAPI and generated client. Workload 13.270 seconds under the unchanged 20-second cap; prior failures remain preserved.
- Prepare the remaining 32 existing PostgreSQL prepared-writer/bounded-loader cases and one combined six-mock/six-static group. Exact source review and execution remain pending.

## Quote candidate formatter correction · 2026-10-17

- Preserve run 39073762410: repository and Ruff passed, then formatter reported a complete 2,616-byte layout diff in three files. Types, OpenAPI and generated client were unrun.
- Apply exactly the retained formatting hunks and prepare only the existing six-command static scope, with unchanged limits. New execution remains pending; no product behavior change.

## Quote candidate integrity corrections · 2026-10-17

- Verify 204 functional/mock checks across nine groups in run 39072574166, including ten canonical-year and NUL-prehydration regressions and 27 actual PostgreSQL cases. Independent identity, result and cleanup review passed.
- Preserve the static job failure: repository check passed, Ruff reported four SIM300 findings, and four later commands were unrun. Correct only the reported comparison ordering and prepare the existing six-command static scope on a new exact branch/workflow pair; execution remains pending.
- Shared legacy-ID rules and chronology policy remain unchanged. [Results and remaining gates](docs/10-spec-development/2026-10-17-quote-integrity-edges.md).

## Quote candidate integration evidence · 2026-10-17

- Verified run 39069601139 on 181579e9: 119 guard cases, 62 database-free product cases and six static/contracts, with zero failures or skips, independent evidence review and owned-container absence. Each workload remained below its unchanged 20-second limit. Broader service/schema integration and activation gates remain open.

## Unreleased · Service-effect logical restore verified

- Verify one real PostgreSQL 18.4 dump/restore and fresh replay case, three phases, in run 39067901565.
- Preserve exact generated metadata, raw payloads, effect IDs and original source state; reject the stale restored incarnation.
- Workload 4.848 seconds; source-bound client versions, cancellation and both absence receipts independently checked.
- Correct reusable PG service fixture identity to match its validated configured database, including ordinary CI's ocwp_e2e; runtime requalification remains pending.
- Prepare four fixed contained integration groups (51/68 guard, 62 pure product boundaries, six static commands); exact results remain pending.
- No capacity or production recovery claim; [integration scope](docs/10-spec-development/2026-10-17-quote-integration-checks.md).
- [Verified scope](docs/10-spec-development/2026-10-17-quote-service-restore.md#verified-tiny-service-effect-restore-result).

## Unreleased · Valid service-effect restore preparation

- Close three PostgreSQL migration integrity cases and nine phases in run 39066342042.
- Prepare one real synthetic PG18.4 dump/restore of generated metadata and valid version-1 service effects, followed by incarnation recovery and exact replay.
- Add pinned signed client preparation inside the existing proof image; retain bounded preparation failure logs.
- Execution and broader integration remain pending; no production restore or capacity claim.
- [Scope](docs/10-spec-development/2026-10-17-quote-service-restore.md).

## Unreleased · PostgreSQL 0013 finite closure and migration integrity preparation

- Verify four PostgreSQL cases and twelve phases in run 39065290465, including guarded NULLs and historical replay.
- Recover exact published source/artifact after workspace replacement; preserve the earlier failed run.
- Prepare three existing refusal, version/reference-integrity and DDL-rollback cases under unchanged limits.
- [Scope](docs/10-spec-development/2026-10-17-quote-migration-integrity.md); restore, concurrency and capacity remain pending.

## Unreleased · PostgreSQL NULL guard assertion correction

- Preserve failed run 39064719886: two cases passed, third SQL-spelling assertion failed, historical case unrun.
- Match the locked compiler's implicit-NULL CASE and directly assert both oversized raw results are NULL.
- Keep product SQL, count guards, no-ORM assertions and resource limits unchanged; corrected qualification pending.
- [Evidence and scope](docs/10-spec-development/2026-10-17-bounded-effects-null.md).

## Unreleased · Bounded-effects PostgreSQL 0013 qualification preparation

- Close eighteen pure cases and all 54 phases on 0b8e3ea9, run 39063614879.
- Prepare four existing PostgreSQL cases with migration chronology observed without implicit upgrades.
- Preserve the same resource budget; actual PostgreSQL result, restore and capacity remain pending.
- [Scope](docs/10-spec-development/2026-10-17-bounded-effects-postgresql.md).

## Unreleased · Pure bounded-effects boundary qualification preparation

- Prepare eighteen existing pure/offline cases with exact collection identity and unchanged limits.
- Preserve static closure; actual functional results and remaining forty-seven cases are pending.
- [Scope](docs/10-spec-development/2026-10-17-bounded-effects-pure.md).

## Unreleased · Bounded-effects static closure

- Independently verify all six static/contract commands on 2460fbc1, run 39061922896.
- Preserve every earlier failure; workload 14.729 s within 20 s, cleanup verified.
- Functional 0013, migration/restore, concurrency and capacity remain pending.

## Unreleased · Typed computed-column adapter

- Record repository/lint/format passes and six strict typing diagnostics in run 39061333413.
- Type the existing SQLAlchemy visitor seam and reflected-column fallback without changing SQL.
- Corrected static and functional verification remain pending.

## Unreleased · Final reported codec and writer formatting

- Retain complete formatter report from run 39060973460; apply its five reviewed hunks.
- Two files changed, 36 previously formatted; exact-source static/runtime checks pending.

## Unreleased · Stable metadata query layout

- Preserve run 39060563945 and its formatter-produced long SQL test line.
- Name the unchanged query locally to satisfy both layout and lint; verification pending.

## Unreleased · Remaining retained formatter sections

- Preserve run 39060197021 and apply its 19 complete reviewed formatting hunks.
- Exclude the truncated codec tail; retain limits and pending verification status.

## Unreleased · Retained bounded-effects test formatting

- Preserve run 39059789509 and apply its next 18 complete reviewed test-format hunks.
- Exclude the incomplete metadata hunk and unseen output; validation remains pending.

## Unreleased · Retained bounded-effects formatter changes

- Record repository/lint passes and formatter output-cap failure in run 39057919833.
- Apply six complete, independently reviewed formatter sections; exclude truncated remainder.
- Preserve limits and failed evidence; complete static/runtime qualification remains pending.

## Unreleased · Bounded-effects remaining line and formatter diagnostics

- Preserve run 39057515145 and its single remaining line-length diagnostic.
- Wrap that select expression and request formatter diff through existing bounded output.
- Corrected-source static and functional verification remain pending.

## Unreleased · Bounded-effects source diagnostic corrections

- Preserve failed static run 39056889116 and its complete 35-issue Ruff output.
- Prepare directly diagnosed source repairs for unchanged bounded static checks.
- Types, contracts and all new runtime evidence remain pending.
- [Scope](docs/10-spec-development/2026-10-17-bounded-effects-source-repair.md).

## Unreleased · Joint bounded-effects static qualification preparation

- Reuse the proven six-command contained profile across 38 Python paths and 13 type roots.
- Product/migration/test sources match the separately reviewed joint snapshot;
  actual checks and all new runtime evidence remain pending.
- [Fixed scope](docs/10-spec-development/2026-10-17-bounded-effects-static.md).

## Unreleased · Bounded versioned quote-order effects preparation

- Close the corrected PostgreSQL-0012 workload on `9c07e224`, run `39053813148`:
  six cases, 18 phases, four real schema identities and verified cleanup.
- Reconcile schema0013 with complete effect reconstruction, bounded full order
  projection validation and measured raw JSON persistence. Source implementation is independently reviewed; tests remain unexecuted.
- Preserve legacy generic data and historical quote-only replay. Refuse unsupported
  populated old receipts before migration DDL; no guessed provenance or truncation.
- Migration, rollback, restore, broader checks and activation remain pending.
  [Selected amendment](docs/02-technical-architecture/2026-10-17-bounded-quote-order-effects.md).

## Unreleased · PostgreSQL settings-result correction

- Preserve failed PostgreSQL run `39053071575`: two DTO passes, first PG call
  failure and three PG cases unrun; cancellation and cleanup verified.
- Replace mapping conversion of SQLAlchemy Result with explicit row iteration.
- Retain bounded short pytest diagnostics for synthetic fixtures without locals.
- Corrected-source qualification remains pending; [scope and evidence](docs/10-spec-development/2026-10-17-postgresql-settings-result-correction.md).

## Unreleased · PostgreSQL-0012 service qualification preparation

- Record six static/contract command passes on `559f9f31` in run `39052034132`.
- Prepare the existing two DTO and four service cases for genuine PostgreSQL
  with isolated schemas and source-bound driver/database/migration evidence.
- Preserve original SQLite fixtures, schema 0012 and containment limits; actual
  PostgreSQL service evidence is pending.
- Scope: [finite PG qualification](docs/10-spec-development/2026-10-17-postgresql-0012-service-qualification.md).

## Unreleased · Static contract subtimeout adjustment

- Record repository, lint, format and strict-mypy passes in run `39051546208`.
  OpenAPI exceeded its three-second subprocess ceiling; client was unrun.
- Allocate OpenAPI six seconds inside the unchanged 20-second workload budget;
  preserve all execution resources, checks and the prior timeout evidence.
- No drift or product latency claim follows from the timeout.
  [Evidence and rationale](docs/10-spec-development/2026-10-17-static-contract-subtimeout.md).

## Unreleased · Observed formatter corrections

- Preserve complete 10,420-byte formatter output from run `39051023447`,
  with no truncation: two files require formatting, 17 already conform.
- Apply only the observed guard/test layout changes. Repository and lint passed;
  format failed and the three later type/contract checks were unrun.
- Keep the bounded static mechanism and all previous results unchanged.

## Unreleased · Direct bounded static output retention

- Record repository and Ruff-lint passes in run `39050280067`, followed by a
  formatter failure whose default diagnostic/diff output escaped the old parser.
- Replace static diagnostic catalogs with bounded original public-source tool
  output, explicit truncation and existing failure/cleanup binding.
- Preserve 16-KiB tool output and execution limits; size the base64 marker and
  service spool explicitly at 24/32 KiB. Actual verification remains pending.
- Scope: [output retention](docs/10-spec-development/2026-10-17-static-output-retention.md).

## Unreleased · Four observed Ruff corrections pending qualification

- Correct SIM905, two RUF043 reports and SIM300 observed in run `39049797128`.
  Preserve fixed rule values, anchored regex behavior and path comparison.
- Repository verification passed; Ruff failed. All four reported diagnostics
  were retained, while one unparsed line keeps the capture explicitly incomplete.
  Format, types and contract checks remain unrun.
- Reuse the existing six-command qualification with unchanged execution limits.

## Unreleased · Actionable static diagnostic preparation

- Retain run `39048370590`: repository passed, Ruff failed with 679 output
  bytes and seven unparsed lines; four later commands were unrun.
- Prepare generic bounded Ruff codes and standard source-only messages in the
  existing diagnostic marker, with explicit incompleteness and unchanged
  execution resources. No remaining product defect is inferred from lost text.
- Scope: [retention correction and evidence](docs/10-spec-development/2026-10-17-static-diagnostic-retention.md).

## Unreleased · Direct static source repair pending qualification

- Preserve the bounded static failure: repository check passed, Ruff failed,
  and format/types/contracts remained unrun. Retain the separate failed repair
  export without claiming a generated patch or known initiating exception.
- Prepare direct style/import repairs on the existing fixed source selection;
  keep rules, product semantics, schema, resource limits and old workflows.
- Reuse the six-command contained qualification on a new exact-source branch.
  Manual inspection is not a passing lint/format/typecheck result.
- Scope: [direct repair and retained evidence](docs/10-spec-development/2026-10-17-direct-static-source-repair.md).

## Unreleased · Fixed service static and contract preparation

- Record independently accepted semantic run `39043072145` on `a9450392`: six
  exact tests, 18 ordered passing phases, zero errors/skips and both final
  absence receipts; the post-append clock assertion executed successfully.
- Prepare six real fixed tool commands: repository check, touched Python lint
  and format, strict touched-production mypy, mounted OpenAPI freshness and
  generated TypeScript-file freshness. Every tool remains unexecuted here.
- Retain the same contained mechanism, 20-second workload and resource ceilings;
  add only closed first-failure path/line/enumerated-rule diagnostics from the
  existing post-stop/reap capped spool, fixed wrappers and explicit image inputs.
- Preserve all product/schema/lock/config/contract bytes and consumed workflows.
  Exact source review and separate publication remain pending; no deployment,
  schema 0013, broad-suite, TypeScript-compilation or activation claim is made.
- Scope: [static and contract preparation](docs/10-spec-development/2026-10-17-quote-service-static-contracts.md).

## Unreleased · Fixed service semantic qualification prepared

- Record independently accepted corrected run `39041920516` on `65e2e69d`:
  six original DTO/SQLite tests and 18 successful ordered phases, zero
  failures/skips/errors, 4.410-second workload and both final absence receipts.
- Prepare one separate six-node semantic batch: two pure fake-driver checks and
  four SQLite refusal/replay/commit-uncertainty/late-expiry cases. Tighten the
  late-expiry test with one assertion proving its post-append hook was reached.
- Change only the fixed guard selector tuple and that assertion, plus a new
  first-run/first-attempt workflow and status documentation. Proven guard logic,
  20-second workload, resources, product code, schema 0012 and locks stay intact.
- Preparation is unexecuted and unpublished. Exact independent review is pending;
  static/contracts, wider semantics, PostgreSQL, capacity and activation stay open.
  Earlier pending entries below are historical checkpoints, not current outcomes.
- Scope: [fixed semantic qualification](docs/10-spec-development/2026-10-17-quote-service-semantic-qualification.md).

## Unreleased · Corrected collection service qualification pending

- Record correction gate `39041234055` on `54fe65be`: eight exact regressions
  passed with zero errors/failures/skips, 1.804-second workload, actual controls,
  cancellation and both final absence receipts independently verified.
- Preserve initial service failure `39039629649`; the synthetic reproduction
  confirms the collection defect but does not recover its discarded runtime error.
- Prepare one separately gated corrected-source qualification of the six original
  service nodes with unchanged guard, fixtures and limits. No application source,
  schema, dependency, selector or prior consumed workflow is changed.
- Service behavior, PostgreSQL, capacity and activation remain unqualified until
  their own evidence exists. The two moved pure driver tests remain unexecuted.

## Unreleased · Initial service collection correction (verification pending)

- Preserve failed single run `39039629649` on `49a6f9d8`: exit 4 during pytest
  bootstrap, 6.395 seconds supervisor time, cancellation and both cleanup receipts
  verified. No six-case service qualification was obtained.
- Separate two pure driver-budget tests from a module-wide indirect database
  parametrization that pytest rejects during collection, even for other selected
  tests. Assertions and the original six selected service nodes are unchanged.
- Prepare bounded, closed failure-stage/count diagnostics; implementation and
  regression execution remain subject to exact review. The discarded original
  diagnostic cannot establish that the collection defect was the only cause.
- Preserve the consumed workflow, schema 0012, limits and all activation gates.
- Prepare a separate fixed eight-node correction gate using the proven frozen
  outer helper and development-only image. One 20-second contained regression
  batch is pending exact wrapper review and execution; no service rerun is implied.

## Unreleased · Reconcile initial six-case service qualification

- Reconcile the frozen 16-file service candidate with current-main tree `323661ad`
  and exact published guard tree `400a69cb`, retaining schema 0012 unchanged.
- Record bootstrap run `39007201961`: 34 finite guard cases passed inside actual
  containment with both cleanup receipts verified. Service behavior remains
  unexecuted; the exact six-node, 20-second qualification still requires review
  and a separately authorized one-shot publication.
- Preserve consumed PR51/PR56/bootstrap history, all wider gates and the frozen
  service source. No schema 0013/version policy or semantic fix is included.

## Historical preparation · Internal quote transaction candidate

- Prepare an unmounted service, closed command DTO and immutable order-effect
  reconstruction with tiny test-first specifications, all execution pending.
- Preserve exact authorized replay, historical null effects and commit-outcome
  uncertainty. No routes, grants, deployment or capacity claim are enabled.
- Execution is blocked until a named contained venue passes actual preflight;
  cooperative checkpoints do not prove a total Python deadline.

## Historical preparation · Closed contained service qualification

- Prepare a fixed six-case service selector, closed result validation and bounded descendant cancellation using existing containment helpers.
- Keep publication/execution blocked pending exact review and independent guard qualification; no tests or workflows have run for this preparation.
- Preserve consumed experiments and record schema 0013/service-version reconciliation as a prerequisite if combined. No service activation follows.

## Unreleased · Reconcile product-stack ordinary evidence

- Record exact PR57 source qualification: 218 retry-free browser executions,
  ordinary runtime/native ARM64/build/security and contained fixed-record success.
- Preserve original browser, maximum/profile and non-qualifying QEMU failures.
  Capacity, latency/contention, activation and physical/operator gates stay open.
- Main integration is authorized and retargeted; exact-candidate verification
  remains pending. The first status checkout used the old PR55 base, so this
  subsequent documentation commit requires fresh CI against main. Earlier
  same-tree evidence is retained separately. No performance claim follows.

## Unreleased · Validate each reconstructed operation result once

- Remove two discarded quote/decision codec calls already performed on the same
  operation-time object by the joined logical-record formatter.
- Keep proof, admission, stored-row, predecessor, outbox, final ledger and canonical
  byte validation; compare tiny histories against an independent frozen PR55 oracle.
- Preserve the failed PR56 diagnostic and verified cleanup. No latency or capacity
  improvement is claimed from reduced codec calls.

## Unreleased · Preserve same-session local sync wake

- Coalesce committed local-write notifications while sync is busy, then dispatch
  unchanged operations after the current successful cycle instead of losing the wake.
- Fence notifications to their original session/network generation; retain offline,
  cancellation and retry behavior, immutable journal and unattributed legacy evidence.
- Reproduce the held-delta race deterministically and preserve QA54's failed first
  browser attempt. Browser timeouts and strict hosted qualification stay unchanged.

## Unreleased · Wait for administration visual identity

- Wait for the exact singleton workshop name before theme captures using the
  existing assertion budget; preserve all geometry and security checks.
- Cover pending, permanent fallback, absent and duplicate identity observations
  with real Playwright assertions outside a browser. Later combined-tree PR57
  browser qualification passed; original PR53/54 failures remain preserved.

## Unreleased · Reconstruct quote operations without repeated prefix ledgers

- Validate chronological quote transitions with normal quote/entry constructors,
  retaining final public ledger/storage validation and every historical record.
- Preserve exact canonical bytes, prefix corruption detection, admission and
  atomicity against an independent frozen PR52 oracle using tiny tests.
- Keep residual row scans and failed capacity evidence visible; no maximum rerun,
  new workflow, higher limits or performance qualification.

## Unreleased · Reuse validated quote-history byte count

- Reuse only the canonical byte count from the same fully validated locked load;
  remove duplicate receipt replay without changing public snapshots or limits.
- Preserve the failed one-shot capacity trial and safe cleanup; tiny equivalence
  and call-count evidence does not establish maximum capacity or latency.

## Unreleased · Prepare contained quote microfixture

- Correct the synthetic evidence reference to a same-length whitespace-free
  identifier after closed diagnostics isolated request decoding; preserve limits.

- Preserve first fixed-record failure with unknown inner cause; add closed phase,
  numeric-byte and safe failure diagnostics without changing shape or deadlines.

- Record independently reviewed hosted micro/cancellation cleanup success; add
  one fixed 100-line/1,000-edge feasibility fixture under unchanged limits.
  Keep original baseline, separate artifacts and maximum capacity gates.

- Preserve the first hosted preflight failure before canary/PG; make bounded Git
  source checks readonly and record closed command-stage/client-exit evidence.

- Add one isolated hosted containment preflight and exactly three synthetic quote
  operations, fresh load and historical retry. No maximum fixture/mode exists.
- Refuse missing resource controllers, identities, counters or cleanup proof;
  preserve private bounded evidence and all existing quote/SQL limits.
- Record PR49 actual-main instrumented closure separately; the original main48
  restart failure still has unknown cause. Capacity and activation remain open.

## Unreleased · Observe bounded API restart lifecycle

- Capture closed, project/API-bound inspect state and finite lifecycle events
  around the disposable smoke harness's existing restart cycles. Preserve
  bounded capture, redaction, original errors, readiness budget and cleanup.
- Retain main48 Runtime 38827236201's failed third restart and unknown cause.
  Instrumentation and synthetic tests do not demonstrate a startup correction.
- No retries, runtime limits, workflows, capacity trial or deployment change.

## Unreleased · Reconcile request contracts with merged reads and catalog

- Normally merge actual main47 `51c35186` into the original PR48 branch, retaining
  the exact request, read-projection, catalog and generated-contract source blobs.
- Preserve both histories and distinguish original hosted evidence from the
  newly combined tree, whose own hosted and postmerge acceptance remain gates.
- PR46 and PR47 are merged; PR48 integration is separately authorized and gated.
  No quote routes, account adoption, schema, capacity trial or deployment is added.

## Unreleased · Bound inactive quote request inputs

- Add closed create/revise and initial customer-decision input contracts with
  bounded actual-byte UTF-8/JSON decoding and fixed non-echoing errors.
- Reuse typed line validation; retain server-owned route outcomes and recording
  identity. No HTTP routes, services, grants, schema or offline behavior change.
- Keep streaming HTTP integration, financial/application admission and activation
  gates explicitly deferred; local decoder tests do not qualify those boundaries.

## Unreleased · Explicit quote catalog compatibility

- Add the three independent quote capability literals to the current 22-grant
  catalog and current Owner starter only. Freeze the legacy seventeen-grant
  wildcard, business set, v1 catalog/role aliases and other current starters.
- Preserve supported old account/token authority, context epochs and minimal
  owner edits. Explicit owner establishment/replacement requires the full current
  snapshot and existing scoped delegation rules; branding adoption stays narrow.
- Regenerate only the two OpenAPI capability-list limits. Qualify fresh/stale v2
  administration parsing without changing frontend production source or protocol.
- Document the unsupported both-side manually preseeded literal exception and
  the existing frontend refusal of duplicate grant snapshots. No quote routes,
  adoption command, real account changes or operational activation are included.

## Unreleased · Prepare bounded quote revision read contracts

- Add closed, exact-integer revision metadata/detail projections from fully
  reconstructed quote snapshots, with separate current lineage context.
- Bound metadata pages to 25, responses to 1 MiB and allowlisted errors to 8 KiB;
  keep proofs/evidence private and bind opaque positions to scope/head/sequence.
- Verify small source-backed corruption, admission and projection cases only.
  Application authority, HTTP/UI exposure and maximum capacity qualification
  remain pending; explicit catalog compatibility is integrated separately.
  No activation or Task 6 completion is claimed.

## Unreleased · Reconcile quote persistence with the reviewed expiry observer

- Normally merge actual main `19882936`, preserving the fixture-only observer
  correction, all mandatory expiry gates and the quote SQL0012/runtime sources.
- Retain the earlier combined PR44 tree's independently verified 27-control
  hosted pass, populated quote restore and three consecutive restart cycles as
  source-bound history; they do not qualify this newly reconciled tree.
- Complete available local qualification: 21 passing controls, zero failures and
  five environment blockers; 2,898 Python passes and 883 frontend passes.
- Keep main45 postmerge CI and new exact-candidate hosted qualification pending.
  Maximum quote capacity, full Task 6 and operational activation remain open.

## Unreleased · Reconcile quote persistence with actual inventory main

- Normally merge main `5ab7dd7c`, preserving its connected inventory read guards,
  privacy/expiry qualification and source exactly alongside quote SQL0012.
- Retain both additive documentation histories and the quote recovery-wrapper
  extension. Full available combined local qualification passed 21 controls
  with five explicit environment blockers; exact merged-head hosted proof remains.

## Unreleased · Require three consecutive API restart qualification cycles

- Strengthen the existing disposable runtime check with three mandatory
  stop/outage/static/start/readiness/branding cycles on the same project.
- Fail immediately on the first error, retaining completed and active cycle
  evidence before existing diagnostics and cleanup. Keep readiness deadlines,
  production startup and the eleven-check total unchanged.
- Preserve the original unexplained restart failure; later one-cycle success
  does not establish its cause. Exact-head three-cycle hosted evidence is pending.

## Unreleased · Match exact PostgreSQL varchar refusal in negative tests

- Preserve the two first-hosted quote schema failures and recognize PostgreSQL's
  exact `StringDataRightTruncation`/`22001` only for the 501-character description
  and reason cases. SQLite still requires its integrity error; other constraint
  cases retain their original exception expectations.
- Assert all six quote tables remain unchanged after each rejected transaction.
  No production schema, bounds or repository behavior changes.

## Unreleased · Retain disposable runtime failure diagnostics

- Capture bounded, redacted container states and log tails before the generated
  Compose fixture is cleaned up. Preserve the original failure and discard
  partial diagnostic output on timeout or overflow.
- Retain PR44's first stop/start readiness failure with unknown cause. Readiness
  deadlines, substantive checks and cleanup remain unchanged; fresh hosted
  runtime and PostgreSQL/restore qualification are still required.

## Unreleased · Quote persistence boundary

- Accept the independently reviewed repository-first quote persistence boundary:
  one lineage per order, immutable history/receipts and exact bounded money.
- Add migration 0012 with scoped immutable quote/evidence/receipt tables, deferred
  head references and replacement/retention guards. Preserve existing history,
  grants and local schema 7; extend the recovery tool's known-schema allowlist
  without changing its old/unknown/multiple-stamp refusals.
- Add bounded immutable storage codecs and finite create/revise/decision proofs,
  with exact safe integers, canonical IDs/time, detached inputs and controlled
  cyclic/deep-input refusals. Preserve existing pure arithmetic and decisions.
- Add transaction-owned quote append/replay and complete-history reconstruction,
  scoped receipt lookup, fresh read-expiry checks and privacy-minimized quote
  outbox facts. Retain caller rollback even with SQLite legacy savepoints.
- Add PostgreSQL contention/restore fixtures to the existing recovery wrapper;
  local skips are explicit and do not claim those gates passed.
- Close independent source findings and pass all available local checks while
  retaining explicit PostgreSQL/restore and hosted qualification gates.
- Keep real PostgreSQL/restore evidence pending and preserve the separate grants,
  routes, all-ingress guards, mixed-writer rollout and operational execution gates.

## Unreleased · Observe expiry inside the disposable browser fixture

- Preserve postmerge main42's mandatory expiry result: nine passes and one CDP
  body-unavailable failure with retries disabled. Direct80, aggregate80 and the
  verifier's27 controls passed, but the workflow correctly failed its repetition
  and final completion gates. Immediate CDP retrieval proved insufficient.
- Observe only the intended actual scoped context response through a test-owned
  fetch clone installed before application bootstrap. Retain only expiry/protocol
  scalars, bound accepted bytes and the accumulation buffer to16 KiB, reject
  missing/ambiguous/invalid responses,
  and attempt cleanup on every exit without awaiting clone reads before returning
  the app response. Closed-page cleanup failure cannot qualify an observation.
- Preserve application fetch arguments, response and errors, all expiry/clock/UI
  assertions and existing45-second budgets. Production and workflow sources are
  unchanged. The separate correction still requires independent review and the
  complete hosted matrix, including ten retry-free native expiry passes.

## Unreleased · Require retry-free inventory expiry evidence

- Run the two existing inventory expiry journeys five times each with one worker,
  zero retries and unchanged 45-second test budgets. Retain a separate native
  browser report and source-bound completion evidence.
- Require all ten fresh passes; skipped, failed, flaky, incomplete or stale
  repetition evidence fails its dedicated check and the aggregate workflow step.
- Local collection proves the exact two titles and ten repeated instances;
  18 gate regressions and 25 repository checks passed. Native repetition remains
  pending and the earlier expiry flake remains retained.

## Unreleased · Bound owned PostgreSQL fixture cleanup

- Preserve the PR42 aggregate's new teardown error: the scoped 20,001-product
  delete exceeded its statement budget during foreign-key checking, although
  all 2,835 test bodies and the separate 43-case PostgreSQL proof passed.
- Delete owned products in ordered batches of at most 500 IDs, bounded by the
  initial row count, requiring exact progress and a final zero count. Keep all
  child/parent cleanup in one rollback-capable transaction and retain foreign data.
- Keep fixture timeouts, production read budgets, foreign keys and indexes intact;
  bind the shared fixture hash into future PostgreSQL evidence. Actual full-module
  and aggregate PostgreSQL validation remains required after this correction.

## Unreleased · Observe inventory reads at the response boundary

- Preserve the next PR42 direct result: 78 first-attempt passes, one case failing
  both attempts and one retry-pass flake. The isolated kernel now starts; actual
  PostgreSQL, both Caddy configurations and runtime/security/build gates passed.
- Exempt only exact POST delta paging from the pending-domain-write observer;
  retain mutation, login/logout, unknown endpoint and lookalike detection plus
  every pending journal, unsent draft, disconnect and reload assertion.
- Read the scoped successful account-context body when its response arrives,
  concurrently with catalog readiness. Missing bodies still fail without retry
  or fabricated expiry. The original CDP failure's precise cause is unproven.
- Keep production sources, expiry/session checks, test budgets and privacy
  unchanged. Corrected hosted direct/repetition/aggregate proof remains required.

## Unreleased · Bind inventory browser checks to real UI contracts

- Preserve the actual PR42 aggregate result: 77 of 80 browser journeys passed;
  three failed on both attempts, with no flaky passes or skipped aggregate cases.
- Verify all six navigation labels and destinations, including Inventario, while
  retaining complete-word, identity, focus, draft, reflow and accessibility checks.
- Prove local-only customer work remains pending with zero attempts, unchanged
  journal/delivery/history and no observed API write requests through inventory
  navigation, disconnection and reload. Do not invent a customer or delivery event.
- Exercise focused radio selection with Space and Escape in every theme; require
  the panel to close and focus to return to its trigger, including default Banco.
- Reconcile actual main43 without changing its quote decision/history sources.
  Hosted corrected kernel/direct/repetition/aggregate and pixel gates remain open.

## Unreleased · Restore the owned kernel-browser fixture

- Keep shared PostgreSQL reset/migration/seed guards closed; seed the isolated
  kernel server's fixed floor-0/floor-1 identities only in its own temporary
  SQLite session. No caller-supplied SQLite URL or guard opt-out is introduced.
- Dispose the owned engine on schema, seed, app-start and serve exceptions.
  Cover both identities, ignored ambient database URLs and direct helper misuse.
- Record actual paired Caddy success and all 43 PostgreSQL cases for the preceding
  PR42 head. Preserve the new kernel startup failure and all earlier evidence;
  the corrected full hosted browser matrix is still required.
- Graceful SIGINT cleanup passed. Preserve the failed SIGTERM smoke and inherited
  SIGTERM/SIGKILL cleanup limits; no signal policy or browser assertions change.

## Unreleased · Match the edge probe to the production image

- Preserve the second PR42 readiness failure: connection refused, container exit
  255, no OOM and clean teardown. The original startup cause is still unproven.
- Build the existing production web Dockerfile for the positive probe. Compare
  immutable raw/production image IDs, equal Caddy binary hashes, file-capability
  semantics and sandboxed version launch before any synthetic private requests.
- Require raw-image EPERM/nonzero and production-image version/zero as paired
  controls. Reject contradictory metadata; keep the same nonroot/read-only/
  cap-drop/no-new-privileges restrictions and both 30-second readiness proofs.
- Bound build/control output and cleanup the unique disposable image tag without
  pruning shared cache. Actual hosted causal and two-config proof remains pending.

## Unreleased · Preserve bounded edge-probe failure diagnostics

- Retain PR42's first actual Caddy readiness failure with its cause unproven;
  the 43-case PostgreSQL proof passed independently. Browser launch failures
  cascaded from the skipped Chromium installation and are not product failures.
- Bound runner subprocess output to 64 KiB and preserve safe phase, health and
  container-state diagnostics. Startup-only log hints publish fixed categories,
  never raw requests, headers, bodies, environment or exception text.
- Preserve original failures separately from container/upstream/directory cleanup
  failures; attempt remaining resource releases. Keep the 30-second readiness
  limit, actual configurations, TLS and every forwarding/privacy assertion.
- This is diagnostic tooling, not a speculative Caddy fix or completed runtime
  qualification. The changed head still requires actual hosted edge/browser proof.

## Unreleased · Bounded connected inventory visibility

- Add read-only catalog, ledger-derived available quantity and bounded live
  movement history in all four themes. Preserve operational form drafts and
  journals; clear volatile inventory on scope/session/owner/expiry/disconnection.
- Add one seven-field movement GET with canonical microsecond/Unicode cursors.
  Preserve old GET contracts, SQL0011/local7/baseline-2, existing grants and commands.
  Revalidate current authority inside bounded read transactions and return no-store.
- Reject unsafe raw numeric wire values rather than showing rounded balances.
  Keep stock/history freshness independent and omit actor/order/reference/note data.
- Cover account-only context access without sync admission, durable owner checks,
  session A→B→A, delayed timers and explicit directory recovery. Add actual-Uvicorn
  privacy proof and fail-closed PostgreSQL/Caddy evidence runners.
- Harden disposable fixture targets and completion evidence; keep credentialed
  test HTTP out of nested browser-report steps with an actual report-only regression.
- Author 17 synthetic browser journeys and four-theme geometry/capture checks.
  Exact integrated native/database/edge/browser/pixel qualification remains pending;
  offline inventory, writes, reconciliation and quote workflows remain open.

## Unreleased · Pure quote decision evidence and partial pricing

- Validate complete immutable quote lineages and stable charge identities without
  changing existing quote revision IDs or integer-minor-unit arithmetic.
- Record approval, rejection and whole-line partial approval with exact revision,
  immutable evidence, append-only current-revision replacements/withdrawals and
  proof-bound replay. Historical receipts remain available after supersession;
  new corrections to superseded evidence are deferred.
- Preserve original full-quote discount shares for selected charges and recompute
  tax on their selected net base. Guard initial order-transition plans against
  stale revisions, replaced evidence and replay without executing the transition.
- Keep this Task 5 sub-slice in memory. Durable timeline delivery, access grants,
  persistence/API/sync/UI and reservation execution remain future increments;
  existing order and inventory behavior is unchanged.

## Unreleased · Finish branding admission after connected startup sync

- Keep one source-bound branding refresh pending until a connected admission's
  first settled sync finishes its operational reads. Clear it on cancellation,
  offline transition or replacement; do not add branding polls to later syncs
  or page navigation. Intermediate progress/transient retries retain the request.
- Reproduce connected login, fresh login while an obsolete response is held, and
  connected reload with preserved v1 personal preferences. Cover real delayed
  logo hashing versus sync writes, finite requests and publication-time changes.
- Preserve the aggregate's two first-attempt identity failures and retry passes,
  separately from its final offline-reload failure. Cache security checks and
  browser assertions/timeouts remain intact; exact hosted evidence is pending.

## Unreleased · Readmit branding after offline startup completes

- Request one current-source offline branding refresh after initial customer,
  order and issue reads settle. Those kernel transactions can legitimately
  invalidate an overlapping cache read by advancing trusted observation time.
- Cover full stored-session restart through both offline and online-hint/network-
  failure paths, real delayed logo/startup-page interleavings, pending-work
  preservation and cancellation before startup completes. Keep the finite
  coalescer, six rollback regressions, cache checks and browser assertions intact.
- Retain the prior candidate's later failure after reload: its before-reload
  verified-copy assertion now passed, but the restored identity was still OCWP.
  Exact changed-head hosted browser qualification remains pending.

## Unreleased · Recover explicitly requested offline branding refresh

- Coalesce a forced branding refresh requested during an active flight into one
  freshly captured/admitted trailing flight. Its finite budget prevents refresh
  notifications from creating a loop; a null cache result alone never retries.
- Reconcile branding after lease validation on a repeated offline notification.
  Preserve conservative cache entry-time rollback, owner, snapshot and expiry
  checks and all existing browser assertions.
- Retain PR41's direct and aggregate offline-branding failures. Add deterministic
  real-controller/kernel/cache coverage, including pending customer work during
  logo validation and rollback/expiry/takeover/future-snapshot refusals. Fresh
  exact-head native/browser and retry-free repetition evidence remains required.

## Unreleased · Preserve branding cache clock-rollback evidence

- Keep the operation-entry timestamp when checking verified context, device
  control and cached-snapshot provenance. Asynchronous elapsed time cannot turn
  an already rolled-back request into an admitted read or write; advancing
  monotonic time still fences lease expiry through the final transaction.
- Add six deterministic read/write rollback regressions, a valid-delay control
  and two late-transaction expiry controls. Preserve PR41's original hosted
  failure and skipped browser gates; this expands its original test-only scope
  with a bounded production cache correction. Exact changed-head hosted evidence
  remains pending.

## Unreleased · Deterministic administration probe clock

- Freeze the test wall date before pausing at the same target, then restore
  advancing Date while paused. Avoid the observed host/browser clock race
  without changing product behavior, timeouts or secret-cleanup assertions.
- Add deterministic installed-Playwright RED/GREEN coverage and a separate
  five-run retry-free browser gate. Preserve the actual postmerge result of
  62 first-pass cases and one retry pass; corrected native evidence is pending.

## Unreleased · Readable transparent logos and native ARM execution criterion

- Select a bounded, presentation-only light/dark image backing from already
  decoded alpha-composited pixels, preserving original logo bytes and personal
  inheritance. Reclaim nested branding-form width for complete button words at
  320 CSS pixels and 200% CSS enlargement; keep existing control targets.
- Require all three ARM64 builds and actual native installed-decoder execution.
  Keep QEMU in a separate non-qualifying diagnostic workflow with its real failed
  status and unproven cause visible. Harden native evidence timing consistency
  without extending the production two-second wall/CPU limits.
- Preserve the previous exact source's 63/63 direct and aggregate browser result
  and native ARM pass. Actual review of 74 original captures found pale-logo and
  enlarged-word defects, so corrected-source execution and pixel review remain
  required. Physical Raspberry and other manual qualification remain open.

## Unreleased · Separate native ARM64 decoder qualification

- Add a public-repository-only standard ARM64 runner probe with verified host,
  container, installed worker and unchanged production decoder bounds.
- Keep QEMU qualification separate and unchanged. Emit only bounded validated
  JSON to the job log/summary, without image, cache or build-record uploads.
  Actual native execution remains pending and does not qualify Raspberry Pi.

## Unreleased · Branding browser selectors and workshop-name reflow checks

- Resolve wrapped palette/scheme selects by their exact accessible combobox
  roles and names, preserving all values, behavior assertions and timeouts.
- Qualify the complete workshop name and intact visible words instead of the
  obsolete single-line `OCWP` assumption. Keep narrow/enlarged layout, focus,
  draft, overflow and accessibility checks; label pre-assertion captures diagnostic.
- Preserve the actual 55/63 browser result as partial evidence. New exact-source
  browser and visual qualification remain required; product UI is unchanged.

## Unreleased · Standalone branding decoder startup

- Keep API-only imports, immutable response DTO and decoder lock out of the
  standalone image child; retain its private immutable PNG record and the exact
  parser, decoder, subprocess contract and resource bounds.
- Preserve both failed QEMU attempts. Local canonical-byte and import-boundary
  regressions pass, with a smaller import graph but no measured native latency
  improvement. Exact changed-image QEMU qualification remains pending.

## Unreleased · Branding qualification setup and ARM diagnostics

- Prepare and validate the private artifact parent before the real recovery
  fixtures run on a clean checkout; retain both required restore proofs.
- Preserve the failed QEMU qualifying attempt and add bounded timeout, exit, CPU
  and separately labelled phase diagnostics. Production decoder limits and
  qualification outcomes are unchanged.

## Unreleased · Shared workshop branding

- Add independently authorized per-workshop name, curated palette and bounded
  canonical logo, explicit shared/personal inheritance and admitted offline reads.
- Freeze historical wildcard/catalog/role-alias semantics, preserve established
  owner edits, and provide explicit synthetic-tested grant adoption.
- Add durable private assets and same-snapshot database-plus-logo recovery.
  Author separate named-volume API/restart/restored-byte and emulated ARM64
  decoder probes while preserving existing runtime and browser recovery checks.
  Native browser, PostgreSQL/restore, Docker/ARM and actual visual qualification
  remain pending for this exact increment; no full MVP or production claim.

## Unreleased · Visible theme verification order

- Verify the selected theme radio before closing its panel, retaining keyboard
  focus-return and exact shell-theme assertions. Fourth hosted run passed 42/43;
  full native and isolated state-matrix visual qualification remains pending.

## Unreleased · Confirmed administration drafts and visual scene isolation

- Mark retained administration drafts clean only after an exact current confirmed
  receipt for their unchanged local revision; preserve newer edits and uncertainty.
- Verify independent themed visual states, intact navigation words and preserved
  focus after label expansion. The prior 41/43 native result remains diagnostic;
  exact corrected native and pixel qualification is still pending.

## Unreleased · Administration role locators and enlarged-layout readability

- Target the exact accessible role combobox in three administration journeys.
  Preserve role values and security assertions after the second hosted run
  passed 41 of 43 cases; complete native and visual qualification remains pending.
- Reflow operational metrics and the compact header from actual available width,
  preventing fragmented words under CSS enlargement while preserving theme DOM.
  Add four-theme complete-word/identity geometry checks and stable full-page capture.

## Unreleased · Connected administration browser corrections

- Preserve the native fetch receiver for administration requests; keep exact
  captures and all request/refusal checks unchanged.
- Guard navigation using current unsent form values rather than past input
  activity, including selector transitions. Saved work no longer produces a
  stale discard prompt; real drafts still require a deliberate decision.
- Preserve all 43 browser journeys, explicitly test cancel/accept for private
  drafts, and qualify 200% CSS zoom at the established 320 CSS-pixel reflow width.
  Exact corrected native and visual evidence remains pending.

## Unreleased · Connected account administration

- Add users/per-user permissions, location creation and self-session controls
  using existing connected APIs, including account-only entry before opening a
  workshop. Preserve exact session fences, four themes and local journals.
- Capture versions, bound owner lookup, clear credential controls synchronously
  and keep uncertain commands unconfirmed without replay. Self-security commands
  lock operational context before dispatch.
- Add synthetic production browser qualification and focused lifecycle/transport
  regressions. Native browser, screenshot, PostgreSQL and disposable-runtime
  evidence remains required on the exact published tree. See
  [scope and evidence](docs/10-spec-development/2026-10-14-connected-administration-ui.md).

## Unreleased · Recovery and selector presentation

- Show closed Spanish labels for retained-work states, with a safe generic label
  for unknown values; preserve original operations and diagnostic fields.
- Separate workshop choices visually and add narrow-screen baseline-progress
  coverage to the existing genuine authenticated browser journey. Hosted visual
  requalification remains required.

## Unreleased · Automatic offline reconnect

- Recover retained offline work automatically when connectivity events/hints are
  stale, using original-lease-bounded, single-flight read-only reachability probes
  before authoritative context verification and any dispatch.
- Preserve exact source/owner/session fences, terminal refusals, pending history
  and disconnects during READY publication; support stale false hints through a
  required new baseline. Local regression evidence does not replace pending
  exact-head hosted browser and eleven-check runtime/restore qualification. See
  [scope and invariants](docs/10-spec-development/2026-10-14-automatic-offline-reconnect.md).

## Unreleased · Offline reload and browser acceptance corrections

- Admit retained offline reload after a genuine network failure even when the
  browser online hint is stale, preserving exact session snapshots, ownership
  fences and existing lease limits through publication. Received refusals never
  become offline authority.
- Observe pinned old-client protocol refusals through a bounded passive fixture
  recorder correlated to the exact request; retain old bundle and queue checks.
- Align accessible order locators, restricted-account local-only expectations and
  temporary-error fixtures with actual production contracts. Independent source
  reviews pass; integrated hosted browser and restore evidence remains pending.

## Unreleased · Audited Python dependency correction

- Upgrade the compatible FastAPI/Starlette pair and PyJWT to bounded patched
  releases, retaining existing application authorization and wire contracts.
- Add regression coverage for malformed Host private-cache policy, JWT parsing
  and preserved signature/expiry rules. The real locked Linux dependency audit
  changes from 19 advisory matches to zero without ignores. Independent local
  review is complete; integrated hosted browser/runtime/security gates remain
  pending. See [applicability and evidence](docs/03-security-privacy/2026-10-14-python-dependency-remediation.md).

## Unreleased · Security scan coverage

- Preserve content-free finding metadata and classify the six findings from the
  first genuine hosted scan as exact synthetic-test or documentation matches.
  Conjunction-scoped exceptions preserve all default rules/history; mandatory
  real-scanner canaries detect modified values and the same values at other paths.

- Correct falsely green secret-history scanning with owner-matched, digest-pinned
  isolated Gitleaks execution and fail-closed error/coverage checks.
- Audit the exact committed Python workspace dependency export with pinned
  pip-audit, complete active-marker coverage and retained input/report evidence.
- Preserve earlier workflow conclusions as historical badges, not proof of
  secret-history or project-lock coverage. Exact-integrated-head hosted evidence
  remains required; application locks and runtime behavior are unchanged. See
  [scope and evidence](docs/10-spec-development/2026-10-14-security-scan-coverage.md).

## Unreleased · Authenticated workshop client C

- Compose genuine authenticated workshop admission, concrete workshop selection,
  captured transports, bounded ongoing deltas and offline reload for the existing
  customer/bicycle/order workflow in a distinct local database.
- Preserve immutable incarnation-bound journals, recovery holds, all four themes
  and exactly scoped preferences; never attribute or replay unknown legacy work.
- Add real pinned old App/SW and disposable floor1 restore acceptance fixtures.
  Source integration and independent review are complete; 21 local aggregate
  checks pass, with exact-final-tree hosted/native qualification still pending;
  normal Compose remains opt-in disabled and no installation was activated. See
  [scope and evidence](docs/10-spec-development/2026-10-14-authenticated-workshop-client.md).

## Unreleased · Server cutover contract

- Add forward-only migration0010, explicit organization compatibility floor and
  restore-resistant signed dataset incarnation; preserve legacy floor0 until opt-in.
- Enforce locked compatibility on every supported writer and actor/full-command
  receipt proofs even when a replay arrives through legacy protocol0.
- Add honest qualified baseline advertisement, closed policy2 client parsing,
  and operator-only monotone activation/expected-incarnation recovery before
  reopening restored APIs. Production App stays v4; no real activation performed.
  See [scope and evidence](docs/10-spec-development/2026-10-14-server-cutover-contract.md).

## Unreleased · Isolated bounded baseline consumer

- Add durable private staging, exact request replay, bounded wire decoding,
  version-dominance merges, completion-proof gates and full partition fences.
- Preserve v1–v5 schema history and every original journal/legacy row.
- Keep actual null advertisement and production App/defaultDB unchanged;
  isolated server/browser qualification is separate from production activation.
  See the [increment record](docs/10-spec-development/2026-10-14-isolated-baseline-client.md).

## Unreleased · Inventory authority and private HTTP responses

- Inventory product/movement commands now refresh persisted session, active
  state, literal grants and scope under the shared organization → actor barrier
  before domain reads or product locks. Existing ledger and replay semantics
  are preserved; PostgreSQL exact-head qualification remains pending.
- Existing identity, administration and location responses are no-store,
  including redirects and sanitized errors. No protocol, schema, credential,
  deployment or production-client activation changes. See the
  [security correction record](docs/10-spec-development/2026-10-14-inventory-authority-barrier.md).

## Unreleased · Bounded authoritative server baselines

- Add durable, identity-bound full scans and finite ordered delta runs, exact
  retry responses, two active device slots and bounded absolute-lived metadata.
- Add migration 0009 and indexed authorized reads with SQL byte-size preflight;
  move the unimplemented quote reservation to 0010. Stored supported long Text
  values are preserved without borrowing REST create-request limits.
- Keep baseline advertisement null pending complete exact-head qualification;
  production v4, inactive kernel, old-writer and restore activation gates remain.
  No deployment, credentials, browser activation or business-data cleanup.

## Unreleased · Isolated server-context adapter

- Add an unactivated, immutable-request adapter for authenticated context, with
  exact configured-realm/scope binding, no-store/redirect rejection, literal
  grants and stale-session/generation fencing. See the
  [increment record](docs/10-spec-development/2026-10-14-isolated-server-context-adapter.md).
- Current null snapshot protocol always returns BASELINE_REQUIRED. Production
  App/auth/defaultDB and all journals remain untouched; preserve old-realm work
  on endpoint moves. Baseline activation and old-writer cutover remain gates.

## Unreleased · Ordered supported change-feed writers

- Customer/bicycle/order REST creates and order transitions now publish the same
  complete projection and outbox event as sync, atomically with domain changes.
- Supported writers serialize per organization before domain reads and cursor
  allocation, sharing administration's lock; HTTP writes refresh actor/session
  authority after waiting and enforce contracted grants/scope, preserving the
  existing literal wildcard-intersection policy.
- Existing numeric feed and REST contracts stay compatible. Historical REST-only
  records still need a baseline. This does not activate a multi-user offline
  cache, backfill inventory/quotes, or fence old server/browser writers.
- First-head hosted PostgreSQL ordering coverage passed; final main30
  reconciliation awaits exact combined-tree hosted qualification.

## Unreleased · Isolated offline identity kernel

- Additive isolated Dexie v5 factory and identity-bound local repository kernel,
  with immutable authored-operation journals, separate delivery history and
  transactionally fenced command/acknowledgement boundaries. Independent review,
  first-head hosted/native-browser proof and the pending main-29 reconciliation
  gate are recorded in the [increment record](docs/10-spec-development/2026-10-14-isolated-offline-identity-kernel.md).
- New isolated contexts remain `BASELINE_REQUIRED`. The production App/default
  singleton and Golden Slice remain v4; authentication-context, complete baseline
  and ordered-feed integration are not implemented. Live shared-browser
  isolation and offline-permission risks remain open; there is no rollout claim.
- Preserve all eight existing stores, personal preferences/logos and unattributed
  legacy queued work. The kernel does not claim, replay or delete legacy rows;
  its [ADR](docs/02-technical-architecture/2026-10-14-isolated-offline-identity-kernel.md)
  records the future activation and operator recovery gates.
- Document the native-Chromium-confirmed Dexie v4-to-v5 old-bundle reopen/write blocker; no
  production activation or schema-version-only fencing claim.
- Move the unimplemented offline quote schema reservation from v5 to v6.
  Administration Alembic 0008 and future quote PostgreSQL 0009 remain unchanged.
  No new credentials, server/wire contract or actual installation upgrade.

## Unreleased · Structural personal themes

- Four structural workshop layouts in Personalización: Banco de trabajo (default),
  Plano técnico, Ritmo modular and Turno nocturno, with twelve curated palettes,
  independent surface schemes and larger Workshop Mode controls.
- Versioned personal preferences in an additive Dexie v4 store; appearance is
  user/organization-local, and a safe offline raster logo also belongs to the
  current location. Shared organization branding and sync are not implemented.
- Shared forms/operations remain mounted during theme changes; order transition
  controls consistently honor the existing orders.write capability.
- Session-generation guards reject late view updates from a previous login or
  scope, preserving current-user conflict/customer context.
- Cached customer/order summaries and per-entity conflict contents require explicit
  read permissions in every theme. Restricted users retain durable records/queues;
  offline permission freshness and safe cache revocation/resnapshot remain pending.
- Conflict types now come from the matching durable queued mutation rather than a
  hardcoded customer label. Legacy ambiguous records stay stored but their details
  are hidden; mismatched/unknown responses cannot acknowledge pending mutations.
- Browser acceptance and screenshots are added; hosted/physical verification
  remains pending until recorded for the exact implementation.

Relevant changes for operators, developers and integrations. Development work
below is unreleased; it does not declare V0.1 physically qualified or V1.0 ready.
Core/API version identifiers retain the current development baseline until an
explicitly qualified release. Changes follow Conventional Commits and DCO;
release versions follow the Engineering specification's SemVer policy.

## Unreleased

### Added

- Unactivated authenticated offline-context endpoint with concrete location scope,
  literal effective grants, durable authorization epoch and bounded signed-token
  lease. Responses are no-store and advertise no snapshot protocol. See the
  [increment record](docs/10-spec-development/2026-10-14-authenticated-offline-context.md);
  no client cache activation, journal migration or deployment is included.

- Bounded server-side local user, starter-role and workshop-location
  administration, with optimistic account versions, session revocation and
  credential-change endpoints. See the
  [scope and acceptance record](docs/10-spec-development/2026-10-14-access-administration.md)
  for evidence and remaining gates; no administration UI or release is claimed.
- Explicit `ocwpctl access create-first-owner` setup creates a separate
  organization-wide owner from a password file. It refuses any existing owner
  record, including inactive owners; existing bootstrap behavior is unchanged.
- Pure quote domain with immutable labor/part/tax/discount lines, integer-minor-unit
  totals, explicit currency, deterministic rounding and scoped discount allocation.
- Quote revisions preserve historical prices, totals and line data. Persistence,
  authorization, API and offline quote editing remain future increments.

- V0.2 Increment 2 Task 3: capability- and location-scoped inventory product
  creation/listing, derived stock reads, and server-authoritative movement API.
- Required UUIDv7 movement IDs provide idempotent command replay. PostgreSQL
  product locks serialize stock reservations and terminal finalization.
- Migration 0007 adds a unique reservation-finalization guard. Existing duplicate
  terminal references block the upgrade without altering history; see the
  [migration and recovery ADR](docs/02-technical-architecture/2026-10-13-inventory-command-atomicity.md).

### Fixed

- Sync chaos setup now waits for durable baseline acknowledgement and proves the
  server baseline/version before constructing the three-operation conflict batch.
  A deterministic delayed-completion/ACK regression and retry-free CI repetitions
  guard the setup race. Hosted red-to-green evidence and ten retry-free
  repetitions are recorded in draft PR #24.

- Consumption now commits its hold finalization and physical stock deduction
  atomically through the API; consuming a reserved item cannot replenish stock.
- Reservation-finalization lookup uses reservation reference IDs and recognizes
  both RELEASE and CONSUME, including distinct command IDs.
- [PR #21](https://github.com/IzignaMx/open-cycling-workshop/pull/21), merged
  2026-10-13: scoped sync payload validation preserves whole-page rollback and
  durable cursors across rejected changes, reload and recovery.

### Security

- `/auth/me` reports revalidated effective session grants and location without
  widening token authority; it serializes its account read with administration.
- Sync service-order transitions attribute new events to the authenticated
  submitter, ignoring legacy payload actor claims. Existing receipt replays must
  match the stored organization/location/entity/operation tuple; mismatches
  become isolated conflicts. Blank or whitespace-containing envelope IDs are
  rejected before effects so domain normalization cannot break identical retry;
  malformed historical receipts remain preserved for explicit reconciliation.
  No receipt actor/digest or client-cache isolation is
  claimed. See the [scope and evidence](docs/10-spec-development/2026-10-14-effective-identity-sync-authority.md).

- Migration test setup excludes ambient application URLs and secret-file
  fallbacks. PostgreSQL infrastructure tests validate dedicated loopback targets
  and pin the raw test URL during Alembic execution; no runtime resolver behavior
  changed. No-network regressions cover target isolation and redacted rejection.

- Administration checks persisted actor/session and old/new target scope/grants
  after acquiring an organization lock. Protected owner designation is separate
  from the `Owner` role bundle; the last active recovery-capable owner cannot be
  removed. New grant snapshots accept only implemented concrete capabilities.
- Sensitive account/session/location changes commit with a secret-free
  append-only audit event. Security changes revoke sessions; name-only changes
  increase account version without revocation. Credential validation errors are
  redacted and sensitive identity/administration request correlation is
  server-generated. Ordinary health request-ID behavior is unchanged.
- Sync pulls enforce the authenticated location when no location is requested
  and filter each known entity by its read capability before pagination. Unknown
  feed types are denied by default; see the
  [scope and cursor decision](docs/02-technical-architecture/2026-10-14-sync-read-authorization.md).

- Inventory commands derive actor/organization/location server-side and reject
  client overrides. Canonical Unicode SKU lengths, bounded pagination and NUL
  text validation prevent malformed requests from becoming storage errors.

### Compatibility and operations

- Identity migration 0008 follows 0007 and adds owner/version metadata and audit
  guards without promoting users or widening existing grants/location scope.
  Invalid legacy session versions block for reviewed remediation. Follow the
  [upgrade and recovery boundary](docs/02-technical-architecture/2026-10-14-access-administration.md).
- Before end-user permission-management rollout, browser state must be isolated
  by user/capability/scope and cursors safely resnapshotted/backfilled while
  preserving pending mutations. Server revocation alone does not satisfy that
  gate. Organization-wide owners remain API-only pending workshop-selector UI.
- Inventory mutations are online commands; no offline stock promise, quote UI,
  public deployment or new release is included.
- Whole-reservation finalization only; partial finalization is explicitly
  rejected. CONSUME responses represent the hold entry; read the stock endpoint
  for the net available balance.
- No historical ledger rows are rewritten or inferred. Quote-table migration
  remains future work and now uses revision 0009 after identity 0008; the earlier
  quote reservation of 0008 is superseded without an empty migration or branch.
- Task 3 verification evidence is tracked in PR #22 and
  [execution status](docs/10-spec-development/execution-state.yaml).
  Physical Windows/Android and other manual V0.1 gates remain open.

### Integration

- Access administration includes merged PR #26 main `c1e2230`, runtime PR #25
  (`0342799`) and migration target-isolation fixes. Its initial PR #27 checkpoint
  `0c37d46` passed PostgreSQL 18.4 CI: 812 Python tests (three explained skips),
  74 frontend core tests, 30 browser executions (10 direct, 10 repeated sync,
  10 qualification) and 27 aggregate checks. All four Local runtime jobs passed, including actual
  backup/restore and three ARM64 image builds. Final integration-head CI and
  browser account/grant/scope cache reconciliation remain separate gates; no
  physical hardware, complete permission UI or production rollout is claimed.
- PR #22 inventory API integrated on 2026-10-14 after fresh independent code review
  and exact-head CI/Security/DCO. Quote Task 4 passed combined-tree CI
  and independent review and was integrated through PR #23; no complete quote workflow or stable release is claimed.

### Local workshop MVP foundation (pending hosted qualification)

- Define the laptop-to-ARM64 workshop MVP sequence, preserving existing tenant/capability and offline-first architecture.
- Add file-based database URL configuration and prevent service-worker navigation fallback from converting API/health routes into application HTML.
- Add isolated local Caddy/PWA/API/PostgreSQL/worker Compose, separate LAN TLS,
  non-superuser application database role and locked amd64/arm64 build paths.
- Add snapshot-consistent PostgreSQL bundles, integrity manifests and guarded
  fresh-target restore; database-only evidence excludes browser queues and assets.
- Local runtime and recovery qualification are tracked in the execution state; this is not a stable release or physical Raspberry qualification.
- Inventory API PR #22 and quote-domain PR #23 are merged; full quote workflow remains future work.

### Qualification reliability

- Inventory PostgreSQL test setup now passes raw percent-encoded URLs to the
  shared migration configuration, avoiding double escaping. A no-network
  regression checks the exact URL and decoded synthetic password before any
  engine can connect; production secret-file handling is unchanged.
