# timezone-safety-check

A static scanner that flags timezone-unsafe `datetime` patterns in Python source: naive constructors, offset-blind parsing, and stamping-instead-of-converting calls. Seven rules, three risk classes, zero network, pure standard library.

## Problem

Naive datetimes are the classic latent production bug: code works on a UTC-deployed laptop, then a server with `TZ=America/New_York` shifts every timestamp by five hours. `datetime.utcnow()` is deprecated since Python 3.12, `strptime` without `%z` silently produces naive objects, and `.replace(tzinfo=...)` *stamps* instead of converting. Code review catches these inconsistently; a deterministic AST pass catches them every time.

## How it works

The scanner parses each `.py` file with the `ast` module and visits every `Call` node:

| Rule | Severity | Pattern |
|---|---|---|
| TZ001 | high | `datetime.utcnow()` — naive by definition |
| TZ002 | high | `datetime.now()` (or `tz=None`) — naive local time |
| TZ003 | medium | `datetime.fromtimestamp(ts)` without a `tz` argument |
| TZ004 | medium | `.replace(tzinfo=...)` — stamps rather than converts |
| TZ005 | medium | `strptime(s, fmt)` where literal `fmt` lacks `%z`/`%Z` |
| TZ006 | info | `astimezone()` with no args on an unproven receiver |
| TZ007 | medium | `fromisoformat("...")` literal without a UTC offset |

Findings carry file, line, col, rule, severity, and message; output is text or JSON; the CLI exits 1 when any finding survives `--min-severity`, so it drops straight into CI.

## Quickstart

```bash
# Scan one file (~0.1s [estimated, repro: time python timezone_safety_check.py scan x.py])
python timezone_safety_check.py scan mymodule.py

# Scan a directory, only medium+, JSON output
python timezone_safety_check.py scan src/ --min-severity medium --format json

# List the rule catalog
python timezone_safety_check.py rules

# Full self-test, 50 checks (~0.2s [estimated, repro: time python self_test.py])
python self_test.py
```

## How this differs (why-not-X)

No direct equivalent found as of 2026-10-11: the R13 precheck searched both rule-named and domain-named queries for a same-mechanism (naive-datetime static scan) repo and returned nothing with anchors. Adjacent tools exist but differ in layer:

| Alternative | Relationship | How this repo differs |
|---|---|---|
| `flake8` + plugins | generic linter framework | needs plugin plumbing and style config; this is a self-contained scanner whose entire rule catalog is one dict, reviewable in a minute |
| `bandit` | security-focused AST linter | targets injection/secrets classes, has no timezone rules; this covers the naive-datetime class exclusively and completely |
| `mypy` | type checker | can flag some misuse via typeshed strictness, but naive vs aware `datetime` are the same type; this scanner works where types cannot distinguish them |

## Minimal Fallback

Without Python tooling, get ~60% of the value with grep:

```bash
grep -rnE "utcnow\(\)|datetime\.now\(\)|fromtimestamp\([^,)]*\)" src/ --include='*.py'
```

It misses `.replace(tzinfo=...)`, `strptime` format analysis, and severity levels — but it is zero-install and catches the highest-severity constructors.

## Design Trade-offs

- **Heuristic receiver matching** — `dt.now()` where `dt` is a datetime *instance* is not flagged (instances have no `.now()`); flagging every `.now()` would drown users in false positives from other libraries.
- **AST over regex** — slightly slower than grep, but immune to comments/strings containing rule text.
- **Seven rules, not twenty** — each rule is explainable in one line; exotic cases (DST-aware arithmetic, zoneinfo misuse) are out of scope on purpose.
- **Exit 1 on findings** — CI-friendly, but means adding the tool to an existing dirty repo needs a baseline/suppression story (not built yet).

## Limits & Second-order Effects

- Cannot prove tz-awareness across function boundaries: `f(dt)` where `f` calls `.astimezone()` is invisible.
- Fixing flagged lines changes runtime behavior *at deploy time* — the diff is safe, the rollout may not be (timestamps written before/after migration differ). Plan a data migration, not just a code fix.
- Teams that blanket-suppress TZ006 (info) tend to stop reading findings at all (alert fatigue).
- Non-Python codebases get nothing; a language-agnostic version would need per-language grammars.

## FAQ

**Is it a linter or a checker?** Either: run it manually, or wire the exit code into CI as a gate.

**Does it execute my code?** Never. Files are only parsed (`ast.parse`); nothing is imported or run.

**Why is `date.today()` not flagged?** `date` has no time component; the naive-vs-aware hazard does not apply.

**When NOT to use this?** Do not use it as your only correctness story for time math (calendar arithmetic, DST gap handling are separate problems); do not trust zero findings as proof of timezone correctness — it is a constructor-and-parsing tripwire, not a semantic analyzer; skip it for code that deliberately works in naive local time end-to-end (e.g., a desktop app with a single-locale display clock).

## [Core Assumptions]

1. The codebase treats "tz-aware UTC everywhere" as the target convention.
2. Heuristic receiver-name matching (`datetime`/`dt` prefixes) trades a few false negatives for near-zero false positives.
3. A finding is advisory: humans confirm intent before changing behavior.
4. Scanned files are valid-or-broken Python text in a UTF-8-compatible encoding; broken files are reported, not crashed on.

---

*Confidence: medium-high — rule mechanics are deterministic and fully self-tested; receiver heuristics are documented approximations. Content as of 2026-10-11.*

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 55 purpose-built AI-engineering tools across neglected niches.

Related tools: [calendar-conflict-check](https://github.com/chenhz01/calendar-conflict-check) · [claim-verification-chain](https://github.com/chenhz01/claim-verification-chain) · [lock-contract-test](https://github.com/chenhz01/lock-contract-test)
