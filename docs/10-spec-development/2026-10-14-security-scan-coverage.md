# Security scan coverage correction · 2026-10-14

Status: implemented, pending independent review and exact-integrated-head hosted
scan evidence. This is a CI qualification correction, not a runtime feature or
release-security qualification.

## Observed defect and traceability

PR #38 Security run [38611517971, job 116015794692](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38611517971/job/116015794692)
reported success for source head `b9da73fa` / tree
`0b5bd4e399dd577b879f2f2a8c7bf524f54cccc6`, but its actual log shows:

- Gitleaks v8.30.1 failed Git's ownership check at `/github/workspace`, logged an
  error, then reported zero commits and zero bytes scanned and no leaks found.
- `uvx pip-audit` had no project input. Its isolated tool environment was not the
  committed application dependency graph.
- REUSE and Trivy had their own results. Trivy's existing policy scans supported
  lockfiles for HIGH/CRITICAL fixable findings and suppresses development/test
  dependencies; it does not establish an unrestricted all-dependency audit.

Earlier green Security badges and recorded clean-scanner summaries remain
historical workflow conclusions. They must not be reused as proof of genuine
Git-history or project-lock coverage without inspecting their actual evidence.
This correction implements the Phase 3 supply-chain/secret-scan requirements,
Phase 5 reproducible CI, Phase 6 security artifacts, and Master Loop's prohibition
on weakening a failing gate or inventing verification.

## Secret history boundary

The checkout still fetches full history, but does not persist credentials or add
Git trust exceptions. The scanner uses the existing upstream v8.30.1 image,
further pinned to the digest actually pulled in the observed job. It runs as the
checkout owner's UID/GID with a read-only checkout, read-only container and no
container network. It receives neither the runner's credentials nor Docker socket.
The image's global Git configuration is ignored, so its built-in wildcard trust
exception is not used. No host/system trust setting changes.

A same-container preflight rejects shallow or unreadable history, identifies HEAD
and counts reachable commits, then traverses the same full patches with checked
Git exit status and no patch logging. Gitleaks scans `--full-history --all HEAD
-m --no-ext-diff`: all fetched refs plus detached candidate HEAD, including merge
patches against parents. The wrapper fails for a nonzero exit, logged scanner/Git
error, missing/ambiguous summary, zero commits or zero bytes, even if the scanner
prints a clean conclusion. Logs use full redaction and omit verbose findings.

The reachable Git count and Gitleaks commit count describe different things:
Gitleaks counts commits contributing scanned fragments; empty, deletion-only or
binary-only history can differ. No false equality claim is made. This is the
pinned scanner's supported Git-text/history scan, not an audit of unreachable
objects, arbitrary binary content or repositories/submodules absent from checkout.
Linked local worktrees are refused because their external Git directory is not in
the mount; use a standalone full clone for actual container scanning.

## Python dependency boundary

The existing pinned uv 0.11.15 exports with `--locked --all-packages --all-groups
--all-extras --no-emit-workspace`. Locked mode refuses metadata/lock drift rather
than rewriting the lock. Local first-party workspace projects are excluded from
third-party vulnerability lookup; all their dependencies remain. Exported package
names and exact versions must equal every registry package in `uv.lock`, and the
lock's SHA256 must stay unchanged. Unsupported non-registry sources fail closed.

PyPA packaging 26.3 runs in an isolated tool environment to evaluate all exported
environment markers. Pinned pip-audit 2.9.0 uses that same Python interpreter and
receives the exact hashed export via `--requirement`, with `--require-hashes
--disable-pip --strict`. It does not resolve new project versions, install project
packages, ignore advisories or fix/upgrade the lock. A successful report must
contain exactly the active exported names/versions, zero skipped dependencies and
zero vulnerabilities. Empty, partial, ambient-tool or drifted reports fail.

The artifact records both the full exported package count and the actual audited
set, marker-excluded versions, full marker environment, Python/platform, input
hashes and tool version. Current Linux CPython 3.13 export has 42 third-party
packages; 40 are active, while colorama 0.4.6 and tzdata 2026.3 are Windows-only.
Those exclusions are disclosed, not claimed as audited. Native Windows and other
marker environments require their own audit evidence.

## Evidence and remaining gates

- The old workflow failed two new contract tests before implementation.
- Focused tests reject false-success zero coverage, logged errors, missing
  summaries, preflight failure, partial/ambient dependency reports, lock changes
  and audit failures. A synthetic real Git history verifies root, side branch,
  merge-only content and detached HEAD all appear in the selected patches.
- The actual pinned uv 0.11.15 export against the unchanged application lock passed
  full package-set validation locally. The real pip-audit 2.9.0 lookup audited all
  40 active packages and **failed** with 19 advisory records: 14 for PyJWT 2.13.0
  and five for Starlette 0.52.1. These are advisory matches, not an application
  exploitability determination. No exception, suppression or dependency upgrade
  was introduced. Separate dependency triage/remediation is now a real gate.
  Preserve `pip-audit.json`, `dependency-input.json` and the failed coverage
  summary; no clean dependency qualification is claimed.
- Focused CI/repository/operations validation: 76 tests passed. The healthy
  Gitleaks byte-summary parser regression was observed failing against the real
  upstream format before correction; static checks and repository contract pass.
- No Docker executable is available locally. Owner-matched Gitleaks execution and
  complete history results remain pending exact-head hosted evidence.
- `security-coverage-${{ github.sha }}` retains redacted scanner logs, preflight,
  hashed dependency input, audit JSON and coverage summaries, including failures.
  A green badge alone cannot close the gate: inspect these artifacts for the
  exact integrated candidate after independent review.
- No runtime/client source, application dependency lock, credentials, real
  installation, deployment or release gate is changed or declared qualified.

## Upstream references

- [Gitleaks v8.30.1 Git mode and redaction](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)
- [Pinned Gitleaks Git source/error behavior](https://github.com/gitleaks/gitleaks/blob/v8.30.1/sources/git.go)
- [Pinned image configuration](https://github.com/gitleaks/gitleaks/blob/v8.30.1/Dockerfile)
- [uv export options](https://docs.astral.sh/uv/reference/cli/#uv-export)
- [pip-audit requirement and strict collection options](https://github.com/pypa/pip-audit/tree/v2.9.0)
