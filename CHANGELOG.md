# Changelog

Relevant changes for operators and implementers. Unreleased work is not a stable
release; package versions remain development baselines until a maintainer-reviewed
SemVer release PR is merged.

## Unreleased

### Added

- Pure quote domain with immutable labor/part/tax/discount lines, integer-minor-unit
  totals, explicit currency, deterministic rounding and scoped discount allocation.
- Quote revisions return the superseded predecessor and appended successor while
  preserving historical prices, totals and line data. Persistence, authorization,
  API and offline quote editing remain future increments.

### Documentation

- Recorded the quote arithmetic/history ADR, test evidence and Task 4 status.
  Physical-device and other release qualification gates remain open.
