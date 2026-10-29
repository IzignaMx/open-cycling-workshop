# Manual Public Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish only the reviewed static presentation through one manually dispatched, exact-source deployment.

**Architecture:** Same-repository allowlisted static build, read-only browser validation, isolated Pages deployment, then separate read-only live verification. No operational application is published.

**Tech Stack:** Existing Python standard library, Playwright/axe and GitHub Pages Actions.

**Spec:** `docs/superpowers/specs/2026-10-27-public-project-presentation-design.md`, with the authorization and bounded refinement below.

## Completion receipt

Completed through the first actual static publication on 2026-10-29; see the
[source-bound receipt](../../10-spec-development/2026-10-28-manual-public-pages.md#first-live-publication--2026-10-29).
Earlier preflight/setup statements below describe the original checkpoint.
No operational app or module activation and no additional dispatch is implied.

## Authority and design refinement

The maintainer authorized preparing/integrating the manual workflow, enabling
Pages with Actions, a main-only github-pages environment and one first validated
publication on 2026-10-28. Technical details below are assistant-selected, not a
claim of separate human design review. This supersedes the earlier permission
block only for static documentation; it does not activate the PWA/API or modules.

Preflight main: bd2dbd6b5a89631e0f95602220cb861c9a6cccc2. Pages is disabled;
no environments exist. The available connector has no supported Pages or
administration mutation endpoint. Check existing authenticated UI availability;
if absent, request operator setup without creating credentials or grants.

## Global Constraints

- Manual workflow_dispatch only; main branch and full expected_source_sha must match github.sha before building and deploying.
- Build and live verification have contents: read only. The deployment job alone has pages: write and id-token: write, no checkout or repository scripts.
- Environment github-pages must select the exact branch main, not tags or the ambiguous protected-branches-only mode. Preserve stronger existing restrictions.
- Upload only artifacts/public-site/open-cycling-workshop, never its parent, repository root or application dist. Build with --require-current.
- Same-run artifact, shared Pages concurrency with cancel-in-progress false, no PAT, configure-pages bootstrap or new credential.
- Build/live jobs 15 minutes, deployment 10 minutes. Existing application budgets and all physical/capacity/install gates remain unchanged.
- No automatic releases or claim of a live URL before returned-origin, exact-byte and actual browser validation.

## Review Focus

- Wrong branch or moving main: guard exact full SHA before any publication.
- Privilege leakage: only the isolated deployment action receives the two writes.
- Artifact substitution/path mistakes: same workflow artifact, exact public leaf and bounded allowlist verification.
- Malicious/redirected returned URL: fixed HTTPS origin and project path, no redirects or arbitrary network destination.
- False qualification: local preview is not live proof; screenshot capture SHA is not deployment SHA.

### Task 1: Guarded workflow

**Files:** `.github/workflows/public-pages.yml`, `tests/repository/test_public_pages_workflow.py`, existing preview trigger list.
**Interfaces:** required string input expected_source_sha; build produces github-pages artifact; deploy produces page_url; verify consumes that URL and a fresh deterministic build at github.sha.

- [x] Write workflow contract tests for exact triggers, permissions, guards, job dependencies, timeouts and upload leaf; observe RED for missing workflow.
- [x] Implement minimal jobs using existing locked browser tools and static builder; no repository scripts in privileged job.
- [x] Run tests GREEN and mutate guards/permissions/artifact path to establish regression sensitivity.

### Task 2: Live proof

**Files:** `scripts/docs/verify_public_site.py`, `tests/repository/test_public_site_deployment.py`, live Playwright config and shared site tests.
**Interfaces:** CLI --url and --directory checks returned URL before any network, bounded no-redirect reads and exact content comparison; live config runs equivalent existing browser checks without starting a localhost server.

- [x] Test bad URL variants, redirects, bad/missing/extra/symlink content and byte mismatches RED.
- [x] Implement finite allowlisted retrieval and source-bound output; verify GREEN.
- [x] Test live configuration destination restrictions and existing local preview equivalence.

### Task 3: Qualification and operator handoff

**Files:** execution-state, manual checklist, public evidence record.

- [x] Record local results and pending hosted/settings/live gates truthfully; independent patch review and fresh full suite.
- [x] Publish draft PR; validate exact source using ordinary CI and native preview. Formal PR approval requires specific confirmation, not blanket delegation.
- [x] Merge only qualified source; fresh postmerge validation. Configure Pages/environment only through supported authorized access, otherwise report operator blocker.
- [x] One manual dispatch of the previously qualified exact main SHA, validate artifact digest, returned URL, deployed bytes, browser/axe and source identity. Preserve failure evidence; no blind reruns.

Provider references checked 2026-10-28: [custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [Pages REST](https://docs.github.com/en/rest/pages/pages). Settings administration is separate from the two deployment token permissions.
