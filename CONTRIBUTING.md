# Contributing

Contributions are welcome from workshop operators, mechanics, implementers, designers, translators, security researchers, and software developers.

## License and DCO

By contributing, you agree that your contribution is licensed under the license applicable to the target component. Core and official application code use `AGPL-3.0-only`.

Every commit must include a Developer Certificate of Origin sign-off:

```text
Signed-off-by: Your Name <you@example.com>
```

Use `git commit -s` to add it automatically.

## Engineering expectations

1. Read the current Foundation, Engineering, QA, and Master Execution specs.
2. Preserve bounded-context boundaries and offline-first invariants.
3. Use tests before production behavior changes.
4. Do not weaken authorization, sync idempotency, privacy, accessibility, or data-recovery guarantees to simplify implementation.
5. Record material architecture changes as ADRs.
6. Keep pull requests reviewable and focused.

## Commit style

Use Conventional Commits. Examples:

```text
feat: add customer mutation ingestion
fix: prevent duplicate sync application
chore: update ci runtime
```

## Your first contribution

1. Follow the [README setup](README.md#get-started), then read [AGENTS.md](AGENTS.md)
   and the current execution state. Identify the requirement and an acceptance test.
2. Create a focused branch. For behavior changes, observe the regression test fail
   before implementing; run it again after the final edit.
3. Run touched lint/type/format checks and the relevant integration/offline/security
   journey. Record unavailable runtimes as blocked, not passed.
4. Update the specification/evidence and add a DCO sign-off. Open a PR explaining
   scope, invariants, exact test commands/results and remaining gates.
5. Wait for independent review and exact-source checks; do not bypass failures.

Documentation, accessibility, translation and workshop workflow expertise are
welcome. For new modules, start with the [compatible-module strategy](docs/08-open-source/2026-10-27-compatible-modules.md).
The SDK is not implemented; do not add a loader, expand legacy grants, write
another domain's tables or invent an unofficial synchronization mechanism.

## A useful, privacy-safe bug report

```text
Source SHA / version:
Operating system, browser and device:
Workflow and connectivity state (online/offline/reconnected):
Minimal steps with synthetic data:
Expected behavior:
Actual behavior:
Reproducibility:
Redacted logs/screenshots (no tokens, customer data or private records):
```

Use public issues only for non-sensitive bugs. For a suspected vulnerability,
follow [SECURITY.md](SECURITY.md) rather than publishing reproduction details.
Do not erase a real browser database to reproduce or fix a problem; preserve its
pending work and use an isolated synthetic profile instead.
