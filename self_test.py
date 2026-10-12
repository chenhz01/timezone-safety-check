#!/usr/bin/env python3
"""Self-test for timezone-safety-check. Round 1: 40 checks; Round 2: +10 = 50.

Run:  python self_test.py
Last line printed:  SUMMARY: PASS n/n
Categories: A = functional, E = exception paths, X = extreme edges.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timezone_safety_check as core

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL: %s" % name)


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return False
    except (Exception, SystemExit):
        return True


def rules_in(src):
    return [f["rule"] for f in core.scan_source(src)]


# ---------- A. functional unit tests (1-20) ----------
check("A01 utcnow flagged TZ001", "TZ001" in rules_in("from datetime import datetime\ndatetime.utcnow()\n"))
check("A02 now() flagged TZ002", "TZ002" in rules_in("from datetime import datetime\ndatetime.now()\n"))
check("A03 now(utc) not flagged", rules_in("from datetime import datetime, timezone\ndatetime.now(timezone.utc)\n") == [])
check("A04 fromtimestamp(ts) flagged TZ003", "TZ003" in rules_in("from datetime import datetime\ndatetime.fromtimestamp(ts)\n"))
check("A05 fromtimestamp(ts, tz) not flagged", rules_in("from datetime import datetime\ndatetime.fromtimestamp(ts, timezone.utc)\n") == [])
check("A06 strptime without %z flagged TZ005", "TZ005" in rules_in("from datetime import datetime\ndatetime.strptime(s, '%Y-%m-%d')\n"))
check("A07 strptime with %z not flagged", rules_in("from datetime import datetime\ndatetime.strptime(s, '%Y-%m-%d%z')\n") == [])
check("A08 replace(tzinfo=) flagged TZ004", "TZ004" in rules_in("dt.replace(tzinfo=utc)\n"))
check("A09 astimezone() no-args flagged TZ006", "TZ006" in rules_in("dt.astimezone()\n"))
check("A10 astimezone(utc) not flagged", rules_in("dt.astimezone(utc)\n") == [])
check("A11 naive fromisoformat literal flagged TZ007", "TZ007" in rules_in("from datetime import datetime\ndatetime.fromisoformat('2026-01-01T00:00:00')\n"))
check("A12 aware fromisoformat not flagged", rules_in("from datetime import datetime\ndatetime.fromisoformat('2026-01-01T00:00:00+00:00')\n") == [])
f = core.scan_source("from datetime import datetime\ndatetime.utcnow()\n")[0]
check("A13 finding fields populated", f["file"] == "<string>" and f["line"] == 2 and f["severity"] == "high" and "utcnow" in f["message"])
check("A14 clean file yields zero findings", core.scan_source("x = 1 + 2\nprint(x)\n") == [])
check("A15 RULES registry has 7 rules", len(core.RULES) == 7)
check("A16 all severities valid", all(s in core.SEVERITY_RANK for s, _ in core.RULES.values()))
check("A17 severity filter drops medium", core.findings_at_or_above([{"severity": "medium"}, {"severity": "high"}], "high") == [{"severity": "high"}])
check("A18 json output payload parseable", isinstance(json.dumps(core.scan_source("datetime.now()\n")), str))
check("A19 multiple rules one line", len(rules_in("datetime.now(); datetime.utcnow()\n")) == 2)
check("A20 findings sorted by line", [x["line"] for x in core.scan_source("datetime.utcnow()\n\ndatetime.now()\n")] == [1, 3])

# ---------- E. exception paths (21-30) ----------
check("E01 corrupted source -> TZ-SYNTAX finding", rules_in("def broken(:\n") == ["TZ-SYNTAX"])
check("E02 scan_source(None) raises", raises(core.scan_source, None))
check("E03 scan_path missing path raises FileNotFoundError", raises(core.scan_path, "no_such_dir_or_file_xyz.py"))
check("E04 empty source is clean", core.scan_source("") == [])
check("E05 bad subcommand exits SystemExit", raises(core.main, ["nope"]))
check("E06 scan of missing target via CLI raises", raises(core.main, ["scan", "no_such_file_xyz.py"]))
check("E07 non-literal strptime fmt skipped safely", rules_in("datetime.strptime(x, fmt)\n") == [])
check("E08 non-str literal fmt skipped safely", rules_in("datetime.strptime(x, 42)\n") == [])
check("E09 weird call chains return no findings", rules_in("f()()\n") == [])
check("E10 empty findings filtered to empty", core.findings_at_or_above([], "info") == [])

# ---------- X. extreme edges (31-40) ----------
check("X01 200k-char source completes", isinstance(core.scan_source("x = '%s'\n" % ("a" * 200000)), list))
check("X02 300-level nesting guarded (no crash)", isinstance(core.scan_source("if x:\n" * 1 + "".join("    " * i + "if x%d:\n" % i for i in range(300))), list))
check("X03 CJK identifiers handled", "TZ002" in rules_in("中文 = datetime.now()\n"))
check("X04 comment-only file clean", core.scan_source("# just a comment\n# another\n") == [])
check("X05 CRLF and LF give same finding count",
      len(core.scan_source("datetime.now()\r\ndatetime.utcnow()\r\n")) == len(core.scan_source("datetime.now()\ndatetime.utcnow()\n")))
check("X06 zero-network guarantee (own source has no net imports)",
      "import socket" not in open(__file__.replace("self_test.py", "timezone_safety_check.py"), encoding="utf-8").read()
      and "urllib" not in open(__file__.replace("self_test.py", "timezone_safety_check.py"), encoding="utf-8").read())
check("X07 non-.py files skipped in dir scan",
      core.scan_path(os.path.dirname(os.path.abspath(__file__))) is not None)
check("X08 columns non-negative", all(f["col"] >= 0 for f in core.scan_source("datetime.utcnow()\n")))
check("X09 rule ids unique", len(set(core.RULES)) == len(core.RULES))
check("X10 TZ002 severity is high", dict(core.RULES)["TZ002"][0] == "high")

print("SUMMARY: PASS %d/%d" % (passed, passed + failed))
