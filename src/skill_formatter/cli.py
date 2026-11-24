"""Command line interface for skillfmt."""

from __future__ import annotations

import argparse
import difflib
import os
import sys
import tempfile
from pathlib import Path

from rich_argparse import RichHelpFormatter

from . import __version__
from .config import ConfigError, load_config
from .formatter import FormatError, FormatResult, format_range, format_source
from .options import CATEGORIES, Options


def _parse_line_range(text: str) -> tuple[int | None, int | None]:
    if ":" not in text:
        raise argparse.ArgumentTypeError("expected a:b")
    left, right = text.split(":", 1)
    try:
        start = int(left) if left else None
        end = int(right) if right else None
    except ValueError as exc:
        raise argparse.ArgumentTypeError("line numbers must be integers") from exc
    if start is not None and start < 1:
        raise argparse.ArgumentTypeError("line numbers are 1-based")
    if end is not None and end < 1:
        raise argparse.ArgumentTypeError("line numbers are 1-based")
    if start is not None and end is not None and end < start:
        raise argparse.ArgumentTypeError("range end must not be before start")
    return start, end


def _parse_categories(text: str) -> set[str]:
    names = {part.strip() for part in text.split(",") if part.strip()}
    unknown = names - set(CATEGORIES)
    if unknown:
        raise argparse.ArgumentTypeError("unknown categories: " + ", ".join(sorted(unknown)))
    return names


def _parse_width(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("width must be an integer") from exc
    if value < 20:
        raise argparse.ArgumentTypeError("width must be >= 20")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillfmt",
        description="Format Cadence SKILL source conservatively.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", metavar="PATH", help="files or directories")
    parser.add_argument("-w", "--write", action="store_true", help="write files in place")
    parser.add_argument("--check", action="store_true", help="check without writing")
    parser.add_argument("--diff", action="store_true", help="print a unified diff")
    parser.add_argument(
        "--lines",
        action="append",
        type=_parse_line_range,
        metavar="A:B",
        help="format only lines A:B (1-based, inclusive; repeatable)",
    )
    parser.add_argument(
        "--width",
        type=_parse_width,
        metavar="N",
        help="line width limit (default: 150, or format.width from config)",
    )
    parser.add_argument("--base-indent", type=int, metavar="N", help="base indentation")
    parser.add_argument("--stdin-path", metavar="PATH", help="file path for stdin input")
    parser.add_argument("--only", type=_parse_categories, metavar="CATS", help="only categories")
    parser.add_argument("--skip", type=_parse_categories, metavar="CATS", help="skip categories")
    parser.add_argument("--config", type=Path, metavar="PATH", help="configuration file")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--best-effort",
        action="store_true",
        help="use conservative layout for unsupported reader syntax",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress warnings")
    parser.add_argument("-v", "--verbose", action="store_true", help="show more details")
    parser.add_argument("--version", action="version", version=f"skillfmt {__version__}")
    return parser


def _apply_cli_options(args: argparse.Namespace, options: Options) -> Options:
    cats = set(options.categories)
    if args.only is not None:
        cats = set(args.only)
    if args.skip is not None:
        cats -= set(args.skip)
    unknown = options.unknown
    if args.strict:
        unknown = "error"
    elif args.best_effort:
        unknown = "conservative"
    return Options(
        width=args.width if args.width is not None else options.width,
        indent=options.indent,
        base_indent=args.base_indent if args.base_indent is not None else options.base_indent,
        categories=frozenset(cats),
        unknown=unknown,
        in_scheme=options.in_scheme,
        case_mode=options.case_mode,
        hanging=options.hanging,
        output_style=options.output_style,
        config_path=options.config_path,
        stdin_path=args.stdin_path,
    )


def _auto_base_indent(text: str) -> int:
    widths = []
    for line in text.splitlines():
        if not line.strip():
            continue
        widths.append(len(line) - len(line.lstrip(" ")))
    return min(widths) if widths else 0


def _format_text(text: str, args: argparse.Namespace, options: Options) -> FormatResult:
    opts = _apply_cli_options(args, options)
    if args.lines:
        return format_range(text, args.lines, opts)
    if opts.base_indent is None and not args.paths:
        opts = Options(
            width=opts.width,
            indent=opts.indent,
            base_indent=_auto_base_indent(text),
            categories=opts.categories,
            unknown=opts.unknown,
            in_scheme=opts.in_scheme,
            case_mode=opts.case_mode,
            hanging=opts.hanging,
            output_style=opts.output_style,
            config_path=opts.config_path,
            stdin_path=opts.stdin_path,
        )
    return format_source(text, opts)


def _write_atomic(path: Path, text: str) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".skillfmt-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _print_warnings(path: str, warnings: list[str], quiet: bool) -> None:
    if quiet:
        return
    for warning in warnings:
        print(f"{path}: warning: {warning}", file=sys.stderr)


def _diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path + " (formatted)",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.only is not None and args.skip is not None:
        parser.error("--only and --skip are mutually exclusive")
    if args.strict and args.best_effort:
        parser.error("--strict and --best-effort are mutually exclusive")
    if args.write and (args.check or args.diff):
        parser.error("--write cannot be combined with --check or --diff")

    stdin_mode = not args.paths or args.paths == ["-"]
    if args.stdin_path and not stdin_mode:
        parser.error("--stdin-path is only valid with stdin")
    if args.write and stdin_mode:
        parser.error("--write cannot be used with stdin")
    if args.lines and len(args.paths) > 1:
        parser.error("--lines accepts only one input file")
    if not stdin_mode and not (args.write or args.check or args.diff) and len(args.paths) != 1:
        parser.error("multiple files require --write, --check or --diff")

    start = Path(args.stdin_path).parent if args.stdin_path else Path.cwd()
    try:
        options = load_config(args.config, start)
    except ConfigError as exc:
        print(f"skillfmt: {exc}", file=sys.stderr)
        return 2

    if stdin_mode:
        raw = sys.stdin.buffer.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            print(f"stdin: {exc}", file=sys.stderr)
            if not (args.check or args.diff):
                sys.stdout.buffer.write(raw)
            return 2
        try:
            result = _format_text(text, args, options)
        except FormatError as exc:
            print(f"stdin: {exc}", file=sys.stderr)
            if not (args.check or args.diff):
                sys.stdout.buffer.write(raw)
            return 2
        _print_warnings("stdin", result.warnings, args.quiet)
        if args.diff:
            diff = _diff("stdin", text, result.text)
            if diff:
                sys.stdout.write(diff)
                return 1
            return 0
        if args.check:
            if result.text != text:
                print("stdin: would reformat")
                return 1
            return 0
        sys.stdout.write(result.text)
        return 0

    failures = 0
    changed = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            failures = 1
            continue
        try:
            result = _format_text(text, args, options)
        except FormatError as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            failures = 1
            continue
        _print_warnings(str(path), result.warnings, args.quiet)
        if result.text == text:
            continue
        changed += 1
        if args.write:
            try:
                _write_atomic(path, result.text)
            except OSError as exc:
                print(f"{path}: {exc}", file=sys.stderr)
                failures = 1
        elif args.diff:
            sys.stdout.write(_diff(str(path), text, result.text))
        elif args.check:
            print(f"{path}: would reformat")
        else:
            sys.stdout.write(result.text)

    if failures:
        return 2
    if (args.check or args.diff) and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
