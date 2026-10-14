# Audited Python dependency remediation · 2026-10-14

## Scope and decision

The genuine project-graph audit of client C base
`8ddf490dac55e1a07b277b7135a44a7c00b0d42d` reported **19 advisories in two
packages**, after alias deduplication: PyJWT 2.13.0 (14) and Starlette 0.52.1
(5). The former audit of the scanner's own environment was not project evidence.

Source remediation is commit `7220fd2b124356dca68c6f5cb32d52ea128c97ea`, tree
`07acb46fb6d5f7e77157b8725bc8e8be7b6e222d`. It changes the platform dependency
manifest, generated lock and one regression test file; no application/auth
implementation, migration, browser storage, deployment or permission changes.
This preserves Foundation ADR-004/013, Phase 3 sections 8/12/18/19/20 and the
Master Agent Loop's deny-by-default, dependency-scan and evidence requirements.
It is a bounded dependency correction, not a new architecture decision.

| Package   | Old lock | New lock | Declared range     |
| --------- | -------- | -------- | ------------------ |
| FastAPI   | 0.128.8  | 0.133.1  | `>=0.133.1,<0.134` |
| Starlette | 0.52.1   | 1.3.1    | `>=1.3.1,<1.4`     |
| PyJWT     | 2.13.0   | 2.15.1   | `>=2.15.1,<2.16`   |

FastAPI 0.128.8 requires Starlette below 1.0; overriding that constraint would
be unsupported. [FastAPI 0.133.0 introduced Starlette 1.x support](https://fastapi.tiangolo.com/release-notes/#01330),
and [0.133.1 metadata](https://pypi.org/pypi/fastapi/0.133.1/json) permits this
pair. Choose the latest patch in that first compatible line rather than
unrelated later feature lines. Starlette is explicitly declared because OCWP
imports its APIs directly and the security floor must survive re-resolution.
[Starlette 1.3.1](https://raw.githubusercontent.com/Kludex/starlette/1.3.1/docs/release-notes.md)
contains all five reported fixes. [PyJWT 2.15.1](https://github.com/jpadilla/pyjwt/releases/tag/2.15.1)
contains the 2.14/2.15 fixes and restores compatibility with trailing Base64URL
padding while continuing to reject non-alphabet junk. The test does not require
rejecting all alternate padding representations.

## Applicability of every original finding

These are application-specific conclusions from source inspection and the
bounded synthetic tests below, not advisory suppressions. All listed packages
were upgraded regardless of whether their optional vulnerable paths were used.
Advisory identifiers link to the original upstream reports.

| pip-audit ID    | Upstream report                                                                                          | Original OCWP applicability                                                                                                                                                                                                                                                                                   | Reported first fix |
| --------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| PYSEC-2026-4145 | [PEM key confusion](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-ffc3-869f-jxw9)           | No mixed symmetric/asymmetric allowlist or raw public-key input; session verification permits only HS256 with a configured secret.                                                                                                                                                                            | 2.14.0             |
| PYSEC-2026-4146 | [Options mutation](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-gvp8-978c-rx2q)            | No reused options mapping or unverified production decode; the library behavior was nevertheless reproduced and retested. See qualification below.                                                                                                                                                            | Unset in advisory  |
| PYSEC-2026-4149 | [DER key confusion](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-p4g4-x82p-q773)           | No mixed algorithm allowlist or DER public verification key.                                                                                                                                                                                                                                                  | 2.14.0             |
| PYSEC-2026-4152 | [Malformed RSA JWK set](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-w6j9-cwv2-h6wq)       | No PyJWKSet/RSA/JWKS path.                                                                                                                                                                                                                                                                                    | 2.14.0             |
| PYSEC-2026-4144 | [JWKS redirect trust](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9v7f-9g4p-ffgj)         | No PyJWKClient or network key retrieval.                                                                                                                                                                                                                                                                      | 2.14.0             |
| PYSEC-2026-4143 | [Empty oct JWK](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9j54-fg26-wv3r)               | No JWK path; SessionTokenService requires a secret of at least 32 characters.                                                                                                                                                                                                                                 | 2.14.0             |
| PYSEC-2026-4148 | [PEM recognizer resource use](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jwrc-g2q2-pq5p) | An HTTP caller does not supply OCWP's configured verification key/certificate.                                                                                                                                                                                                                                | 2.14.0             |
| PYSEC-2026-4140 | [Unknown-kid JWKS refresh](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-2gx3-rcp4-g85q)    | No PyJWKClient or key-id-driven network refresh.                                                                                                                                                                                                                                                              | 2.14.0             |
| PYSEC-2026-4141 | [Deep unverified payload](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v)     | OCWP verifies signatures before payload JSON decoding; unsigned payload is rejected. The advisory's unverified decode path was reproduced separately.                                                                                                                                                         | 2.15.0             |
| PYSEC-2026-4147 | [Non-alphabet compact JWS](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-hxm8-2xgr-2p9m)    | Alternate serialization of a real issued session was accepted. OCWP does not use a raw-token denylist, so no revocation bypass is claimed; new regression rejects the junk suffix.                                                                                                                            | 2.14.0             |
| PYSEC-2026-4151 | [Public JWK containers](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-w2cx-738m-mc7w)       | No mixed algorithm allowlist or public JWK/JWKS key input.                                                                                                                                                                                                                                                    | 2.14.0             |
| PYSEC-2026-4150 | [BOM/encoding key confusion](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-r6x4-923q-g947)  | No mixed algorithm allowlist or raw public JWK input.                                                                                                                                                                                                                                                         | 2.14.0             |
| PYSEC-2026-4142 | [Deep unsigned header](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-8wjv-2p76-3863)        | Reachable in SessionTokenService before signature checking; a bounded deep header escaped as RecursionError. Normal generic bearer dependency catches all exceptions; context's narrower handler did not. Upstream now raises InvalidTokenError. Real ingress header-size limits remain deployment-dependent. | 2.14.0             |
| PYSEC-2026-4183 | [OKP public/private mismatch](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-x33g-cr3x-6449) | No OKP, private JWK or sender-constrained-token import.                                                                                                                                                                                                                                                       | 2.15.0             |
| PYSEC-2026-161  | [Host URL reconstruction](https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr)   | Demonstrated: slash/query/fragment in Host made middleware misclassify `/auth/me`; both authenticated 200 and unauthenticated 401 lacked no-store. Routing/authentication still ran.                                                                                                                          | 1.0.1              |
| PYSEC-2026-249  | [URL-encoded form bounds](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq)   | Current API uses JSON schemas; no request.form/FormParser path or python-multipart dependency.                                                                                                                                                                                                                | 1.3.1              |
| PYSEC-2026-248  | [Path URL reconstruction](https://github.com/Kludex/starlette/security/advisories/GHSA-jp82-jpqv-5vv3)   | Direct ASGI request construction reproduces authority confusion. No current OCWP hostname-based authorization/SSRF sink found; malformed-path delivery through deployed ingress is not claimed.                                                                                                               | 1.3.0              |
| PYSEC-2026-2281 | [Windows StaticFiles UNC](https://github.com/Kludex/starlette/security/advisories/GHSA-wqp7-x3pw-xc5r)   | Backend does not mount StaticFiles. No physical Windows qualification is implied.                                                                                                                                                                                                                             | 1.1.0              |
| PYSEC-2026-2280 | [HTTPEndpoint dispatch](https://github.com/Kludex/starlette/security/advisories/GHSA-x746-7m8f-x49c)     | Backend uses explicit FastAPI routes and no HTTPEndpoint subclasses.                                                                                                                                                                                                                                          | 1.1.0              |

### Advisory with no recorded patched version

GHSA-gvp8-978c-rx2q's upstream page records an affected range of
`>=2.11.0, <=2.13.0`, while leaving the patched version unset. Do not describe
that metadata as a maintainer declaration that a particular release fixes it.
[The official 2.15.1 source](https://raw.githubusercontent.com/jpadilla/pyjwt/2.15.1/jwt/api_jwt.py)
copies the input options in `_merge_options`. PyJWT 2.13.0 was independently
observed mutating the shared dictionary and accepting an expired token after
signature checking was re-enabled. The 2.15.1 regression preserves the input
dictionary and rejects the same expired token. Its current PyPI vulnerability
response and the complete project audit contain no finding for this version.
Thus there is **no unresolved reported advisory in this candidate's audit**;
the metadata qualification remains explicit. No ignore or exception was added.

OCWP's production call in `identity/security.py` already creates fresh options,
keeps signature verification enabled and revalidates expiry/iat/nbf against its
injected clock. That security policy and post-lock revalidation are unchanged.

## Reproducible evidence and provenance

All artifacts below are local generated evidence under
`artifacts/dependency-remediation/`, not committed files or hosted qualification.
An isolated worktree-local virtual environment was used; shared environments
were not updated. Baseline compatibility used Python 3.13.5. The lock update,
candidate frozen sync and export used the project's pinned uv **0.11.15**.
Only three third-party lock records and the workspace dependency metadata
changed. Every existing unrelated package version/hash and the official
`https://pypi.org/simple` source were preserved.

```sh
uv lock --upgrade-package 'fastapi==0.133.1' \
  --upgrade-package 'starlette==1.3.1' --upgrade-package 'PyJWT==2.15.1'
uv sync --all-packages --group dev --locked
uv export --all-packages --group dev --locked --no-emit-workspace \
  --no-header --format requirements-txt \
  --output-file artifacts/dependency-remediation/python-requirements.txt
pip-audit --disable-pip --no-deps --require-hashes \
  -r artifacts/dependency-remediation/python-requirements.txt \
  -f json -o artifacts/dependency-remediation/pip-audit.json
```

The actual commands also selected writable isolated cache directories. pip-audit
**2.9.0** returned exit 0, zero vulnerabilities and zero skipped dependencies.
The export covers all **42** registry packages in the lock, including runtime
and dev groups. All **40** active Linux/Python 3.13 packages were audited;
`colorama==0.4.6` and `tzdata==2026.3` are inactive environment markers, not
silently ignored findings. The already-reviewed scanner validator from
`60cf631` independently checked exact lock/export/audit membership. See
`audit-coverage.json`. This does not claim a Windows environment audit.

New `test_dependency_security.py` has **14** cases. The final file was run in
another isolated environment with the original hashed dependency export:
**11 expected failures, 3 passing controls** (`regression-final-red.log`). The
candidate passes all 14 (`regression-green.log`). Controls retain
HS256-only verification, valid principal round trips and injected-clock expiry.
Deep test input is bounded to 100,000 bytes before Base64URL encoding. The
unverified-payload case explicitly distinguishes the unused library path from
OCWP's verified path. No real credentials or remote target were used.

- Full final Python suite: **1595 passed, 189 explicit PostgreSQL skips**;
  no PostgreSQL test URL was configured (`pytest-final.log`).
- Full Ruff lint/format: pass (193 Python files formatted).
- Strict mypy: pass (90 source files).
- OpenAPI export and generated TypeScript checks: pass, no contract changes.
- Repository contract and `git diff --check`: pass.
- Real Uvicorn/SQLite HTTP smoke: pass, including login, readiness, mutation
  application and customer pull. SQLite does not prove PostgreSQL concurrency.
- One visible upstream Starlette warning recommends future migration of its
  TestClient from httpx to httpx2. The existing httpx 0.28.1 remains supported
  and all current tests retain it; no warning filter or extra dependency added.

## Remaining qualification

An independent checksum-verified Gitleaks 8.30.1 local history scan at source
commit `7220fd2` covered 318 commits / 16,138,214 bytes. It reported the same
six previously classified false positives in historical README prose and
synthetic log-redaction fixtures, with no findings in this dependency patch or
new test. Its raw exit code remains **1**, and this patch adds no suppression.
This is useful coverage evidence, not a clean full-security verdict.

Independent patch review and exact integrated-head hosted security/CI remain
separate gates. The scanner correction was developed on another branch; this
dependency-only base does not itself contain that correction. Integration must
combine both before relying on hosted Security. Gitleaks disposition, image
scanning, PostgreSQL, native browser/service-worker/restore and physical-device
gates are not closed by this dependency audit. No production installation,
credential, deployment, activation or migration was touched.
