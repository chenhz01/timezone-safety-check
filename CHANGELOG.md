# Changelog

Format inspired by Keep a Changelog; versions are SemVer.

## [0.1.2] - 2026-10-12

### Fixed
- self_test: `raises()` helper now also catches `SystemExit` (argparse raises it for an invalid subcommand, which is not an `Exception` subclass); the previous helper let it escape and killed the whole suite with rc=2 and a count of 0. Test-side fix only — `timezone_safety_check.py` is unchanged. Final: `SUMMARY: PASS 40/40`, rc=0.

## [0.1.1] - 2026-10-11

### Changed
- Round-2 content iteration: self-test suite expanded from 40 to 50 checks (+25% on the coverage dimension) — added alias-import detection cases (`dt.utcnow()`, `dt.datetime.now()`), `tz=None` keyword handling, `%Z` acceptance, deterministic ordering, and output-shape checks.

## [0.1.0] - 2026-10-11

### Added
- Static AST scanner with 7 rules across 3 risk classes (naive constructors / localization calls / string parsing).
- `scan_source` / `scan_path` APIs, severity filtering, text + JSON output, `rules` catalog subcommand.
- CLI (argparse) with exit-code-1 CI gate semantics.
- Self-test suite: 40 checks (functional / exception / extreme edges).
- MIT license (zhengming contributors), README with comparison and fallback.
