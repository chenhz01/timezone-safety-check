#!/usr/bin/env python3
"""timezone-safety-check: static scanner for timezone-unsafe datetime patterns.

Three risk classes, seven rules, zero network, pure standard library:
  TZ001 naive utcnow()          TZ005 strptime without %z
  TZ002 naive now()             TZ006 unproven astimezone()
  TZ003 local fromtimestamp()   TZ007 naive fromisoformat literal
  TZ004 replace(tzinfo=...) stamping
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

__version__ = "0.1.1"

RULES = {
    "TZ001": ("high", "datetime.utcnow() returns a naive datetime (deprecated since 3.12); use datetime.now(timezone.utc)"),
    "TZ002": ("high", "datetime.now() without a tz argument returns a naive local datetime; pass tz=timezone.utc"),
    "TZ003": ("medium", "datetime.fromtimestamp() without a tz argument depends on the machine's local timezone"),
    "TZ004": ("medium", ".replace(tzinfo=...) stamps rather than converts; confirm the intended offset"),
    "TZ005": ("medium", "strptime format lacks %z/%Z; the parsed datetime will be naive"),
    "TZ006": ("info", "astimezone() called with no args on an unproven receiver; confirm it is tz-aware"),
    "TZ007": ("medium", "fromisoformat() literal has no UTC offset; result will be naive"),
}
SEVERITY_RANK = {"info": 0, "medium": 1, "high": 2}


def _dotted_name(node):
    """Return the dotted path of a call target as a tuple, or None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return tuple(parts)
    return None


def _const_str(node):
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError, RecursionError):
        return None
    return value if isinstance(value, str) else None


def _is_none_const(node):
    return isinstance(node, ast.Constant) and node.value is None


class _Visitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.findings = []

    def _add(self, node, rule):
        severity, message = RULES[rule]
        self.findings.append({
            "file": self.filename,
            "line": getattr(node, "lineno", 0),
            "col": getattr(node, "col_offset", 0),
            "rule": rule,
            "severity": severity,
            "message": message,
        })

    def visit_Call(self, node):
        dotted = _dotted_name(node.func)
        if dotted:
            last = dotted[-1]
            prev = dotted[-2] if len(dotted) >= 2 else None
            if last == "utcnow" and not node.args and not node.keywords:
                if prev == "datetime" or len(dotted) == 2:
                    self._add(node, "TZ001")
            elif last == "now" and not node.args:
                if all(kw.arg == "tz" and _is_none_const(kw.value) for kw in node.keywords):
                    if prev == "datetime" or (len(dotted) == 2 and dotted[0].lower().startswith("dt")):
                        self._add(node, "TZ002")
            elif last == "fromtimestamp" and prev == "datetime" and len(node.args) < 2 \
                    and not any(kw.arg == "tz" for kw in node.keywords):
                self._add(node, "TZ003")
            elif last == "strptime" and prev == "datetime" and len(node.args) >= 2:
                fmt = _const_str(node.args[1])
                if fmt is not None and "%z" not in fmt and "%Z" not in fmt:
                    self._add(node, "TZ005")
            elif last == "fromisoformat" and prev == "datetime" and node.args:
                literal = _const_str(node.args[0])
                if literal is not None and "+" not in literal and not literal.rstrip().endswith("Z"):
                    self._add(node, "TZ007")
            elif last == "replace":
                if any(kw.arg == "tzinfo" for kw in node.keywords):
                    self._add(node, "TZ004")
            elif last == "astimezone" and not node.args and not node.keywords:
                self._add(node, "TZ006")
        self.generic_visit(node)


def scan_source(source, filename="<string>"):
    """Scan one Python source string; returns a list of finding dicts."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [{"file": filename, "line": exc.lineno or 0, "col": exc.offset or 0,
                 "rule": "TZ-SYNTAX", "severity": "info",
                 "message": "source does not parse: %s" % exc.msg}]
    except RecursionError:
        return [{"file": filename, "line": 0, "col": 0, "rule": "TZ-SYNTAX",
                 "severity": "info", "message": "source too deeply nested to parse"}]
    visitor = _Visitor(filename)
    visitor.visit(tree)
    findings = visitor.findings
    findings.sort(key=lambda f: (f["line"], f["col"]))
    return findings


def scan_path(path):
    """Scan a .py file or a directory tree of .py files. Raises FileNotFoundError."""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return scan_source(fh.read(), path)
    if os.path.isdir(path):
        findings = []
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for name in sorted(files):
                if name.endswith(".py"):
                    findings.extend(scan_path(os.path.join(root, name)))
        return findings
    raise FileNotFoundError("no such file or directory: %s" % path)


def findings_at_or_above(findings, min_severity):
    rank = SEVERITY_RANK.get(min_severity, 0)
    return [f for f in findings if SEVERITY_RANK.get(f["severity"], 0) >= rank]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="timezone-safety-check", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan", help="scan a .py file or a directory")
    p_scan.add_argument("target")
    p_scan.add_argument("--min-severity", choices=list(SEVERITY_RANK), default="info")
    p_scan.add_argument("--format", choices=["text", "json"], default="text")
    sub.add_parser("rules", help="list all rules")
    args = parser.parse_args(argv)
    if args.command == "rules":
        for rule, (severity, message) in sorted(RULES.items()):
            print("%s [%s] %s" % (rule, severity, message))
        return 0
    findings = findings_at_or_above(scan_path(args.target), args.min_severity)
    if args.format == "json":
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    else:
        for f in findings:
            print("%s:%s:%s: %s [%s] %s" % (f["file"], f["line"], f["col"],
                                            f["rule"], f["severity"], f["message"]))
        print("%d finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
