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
