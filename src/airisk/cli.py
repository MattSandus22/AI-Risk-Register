"""airisk validate | report | coverage"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import __version__
from .coverage import iso_coverage, nist_coverage, summary
from .loader import RegisterError, build, load_raw
from .report import RENDERERS, build_view
from .validate import errors, validate


def _load(args):
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    raw = load_raw(args.register)
    issues = validate(raw, as_of)
    return raw, issues, as_of


def cmd_validate(args) -> int:
    _, issues, _ = _load(args)
    for i in issues:
        print(i)
    n_err, n_warn = len(errors(issues)), len(issues) - len(errors(issues))
    print(f"\n{n_err} error(s), {n_warn} warning(s)")
    if n_err or (args.strict and n_warn):
        return 1
    return 0


def cmd_report(args) -> int:
    raw, issues, as_of = _load(args)
    if errors(issues):
        for i in errors(issues):
            print(i, file=sys.stderr)
        print("Fix the errors above before generating a report (run `airisk validate`).", file=sys.stderr)
        return 1
    view = build_view(build(raw), issues, as_of)
    out = RENDERERS[args.format](view)
    if args.output:
        Path(args.output).write_text(out)
        print(f"Wrote {args.format} report -> {args.output}")
    else:
        sys.stdout.write(out)
    return 0


def cmd_coverage(args) -> int:
    raw, issues, _ = _load(args)
    if errors(issues):
        print("Register has errors; run `airisk validate` first.", file=sys.stderr)
        return 1
    reg = build(raw)
    for title, rows in (("NIST AI RMF", nist_coverage(reg)), ("ISO/IEC 42001", iso_coverage(reg))):
        s = summary(rows)
        print(f"{title}: {s['Covered']} covered, {s['Planned']} planned, {s['Gap']} gaps")
        for r in rows:
            print(f"  {r.status:8} {r.ref:10} {r.title}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airisk", description="AI risk register as code")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("register", help="register directory (systems.yaml, risks.yaml, ...)")
        sp.add_argument("--as-of", help="evaluate review dates as of YYYY-MM-DD (default: today)")

    v = sub.add_parser("validate", help="check data quality and governance rules")
    common(v)
    v.add_argument("--strict", action="store_true", help="treat warnings as failures (for CI)")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("report", help="generate a report")
    common(r)
    r.add_argument("--format", choices=sorted(RENDERERS), default="html")
    r.add_argument("-o", "--output", help="output file (default: stdout)")
    r.set_defaults(func=cmd_report)

    c = sub.add_parser("coverage", help="show NIST AI RMF and ISO/IEC 42001 coverage")
    common(c)
    c.set_defaults(func=cmd_coverage)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RegisterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
