"""Command line interface for skillfmt."""

from __future__ import annotations

import argparse
import difflib
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn, cast

from rich_argparse import RawDescriptionRichHelpFormatter

from . import __version__
from .config import ConfigError, load_config, render_template
from .formatter import FormatError, FormatResult, format_range, format_source
from .i18n import TEXTS, detect_language
from .i18n import text as tr
from .options import CATEGORIES, Options


def _parse_line_range(text: str, lang: str = "en") -> tuple[int | None, int | None]:
    if ":" not in text:
        raise argparse.ArgumentTypeError(tr(lang, "err_range_format"))
    left, right = text.split(":", 1)
    try:
        start = int(left) if left else None
        end = int(right) if right else None
    except ValueError as exc:
        raise argparse.ArgumentTypeError(tr(lang, "err_range_integer")) from exc
    if start is not None and start < 1:
        raise argparse.ArgumentTypeError(tr(lang, "err_range_one_based"))
    if end is not None and end < 1:
        raise argparse.ArgumentTypeError(tr(lang, "err_range_one_based"))
    if start is not None and end is not None and end < start:
        raise argparse.ArgumentTypeError(tr(lang, "err_range_order"))
    return start, end


def _parse_categories(text: str, lang: str = "en") -> set[str]:
    names = {part.strip() for part in text.split(",") if part.strip()}
    unknown = names - set(CATEGORIES)
    if unknown:
        joined = ", ".join(sorted(unknown))
        raise argparse.ArgumentTypeError(tr(lang, "err_category_unknown").format(names=joined))
    return names


def _parse_width(text: str, lang: str = "en") -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(tr(lang, "err_width_integer")) from exc
    if value < 20:
        raise argparse.ArgumentTypeError(tr(lang, "err_width_minimum"))
    return value


def build_parser(lang: str | None = None) -> argparse.ArgumentParser:
    lang = lang or detect_language()
    strings = {key: tr(lang, key) for key in TEXTS[lang]}

    class LocalizedFormatter(RawDescriptionRichHelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):  # type: ignore[no-untyped-def]
            super().add_usage(usage, actions, groups, prefix=prefix or strings["usage"])

    class LocalizedParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            self.print_usage(sys.stderr)
            self.exit(2, f"{self.prog}: {strings['error_label']}: {message}\n")

    def parse_line_range(value: str) -> tuple[int | None, int | None]:
        return _parse_line_range(value, lang)

    def parse_categories(value: str) -> set[str]:
        return _parse_categories(value, lang)

    def parse_width(value: str) -> int:
        return _parse_width(value, lang)

    parser = LocalizedParser(
        prog="skillfmt",
        description=strings["description"],
        epilog=strings["epilog"],
        formatter_class=LocalizedFormatter,
        add_help=False,
    )
    parser.add_argument("paths", nargs="*", metavar="PATH", help=strings["paths"])
    parser.add_argument("-w", "--write", action="store_true", help=strings["write"])
    parser.add_argument("--check", action="store_true", help=strings["check"])
    parser.add_argument("--diff", action="store_true", help=strings["diff"])
    parser.add_argument(
        "--lines",
        action="append",
        type=parse_line_range,
        metavar="A:B",
        help=strings["lines"],
    )
    parser.add_argument(
        "--line-width",
        type=parse_width,
        dest="line_width",
        metavar="N",
        help=strings["line_width"],
    )
    parser.add_argument("--base-indent", type=int, metavar="N", help=strings["base_indent"])
    parser.add_argument("--stdin-path", metavar="PATH", help=strings["stdin_path"])
    parser.add_argument("--only", type=parse_categories, metavar="CATS", help=strings["only"])
    parser.add_argument("--skip", type=parse_categories, metavar="CATS", help=strings["skip"])
    parser.add_argument("--config", type=Path, metavar="PATH", help=strings["config"])
    parser.add_argument("--strict", action="store_true", help=strings["strict"])
    parser.add_argument(
        "--best-effort",
        action="store_true",
        help=strings["best_effort"],
    )
    parser.add_argument(
        "--config-template",
        action="store_true",
        help=strings["config_template"],
    )
    parser.add_argument("-q", "--quiet", action="store_true", help=strings["quiet"])
    parser.add_argument("-v", "--verbose", action="store_true", help=strings["verbose"])
    parser.add_argument("-h", "--help", action="help", help=strings["help"])
    parser.add_argument(
        "--version",
        action="version",
        version=f"skillfmt {__version__}",
        help=strings["version"],
    )
    language = parser.add_mutually_exclusive_group()
    language.add_argument("--zh", action="store_true", help=strings["force_zh"])
    language.add_argument("--en", action="store_true", help=strings["force_en"])
    parser._positionals.title = strings["positional"]
    parser._optionals.title = strings["options"]
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
        width=args.line_width if args.line_width is not None else options.width,
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


def _expand_inputs(raw_paths: list[str], lang: str) -> tuple[list[Path], bool]:
    paths: list[Path] = []
    failed = False
    for raw in raw_paths:
        path = Path(raw)
        if not path.is_dir():
            paths.append(path)
            continue
        found = sorted(
            {*path.rglob("*.il"), *path.rglob("*.ils")},
            key=lambda item: str(item),
        )
        if not found:
            print(f"{path}: {tr(lang, 'no_skill_files')}", file=sys.stderr)
            failed = True
        paths.extend(found)
    return paths, failed


def _print_warnings(path: str, warnings: list[str], quiet: bool, lang: str) -> None:
    if quiet:
        return
    label = tr(lang, "warning_label")
    for warning in warnings:
        print(f"{path}: {label}: {warning}", file=sys.stderr)


def _print_verbose(args: argparse.Namespace, path: str, changed: bool, lang: str) -> None:
    if not args.verbose:
        return
    key = "verbose_changed" if changed else "verbose_unchanged"
    print(tr(lang, key).format(path=path), file=sys.stderr)


def _reconfigure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            cast(Any, stream).reconfigure(encoding="utf-8", errors="replace", newline="\n")


def _diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path + " (formatted)",
        )
    )


def _prescan_language(argv: list[str]) -> str | None:
    for arg in argv:
        if arg == "--":
            break
        if arg == "--zh":
            return "zh"
        if arg == "--en":
            return "en"
    return None


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdio()
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser(_prescan_language(arguments))
    args = parser.parse_args(arguments)
    lang = "zh" if args.zh else "en" if args.en else detect_language()
    if args.only is not None and args.skip is not None:
        parser.error(tr(lang, "err_only_skip"))
    if args.strict and args.best_effort:
        parser.error(tr(lang, "err_strict_best_effort"))
    if args.quiet and args.verbose:
        parser.error(tr(lang, "err_quiet_verbose"))
    if args.write and (args.check or args.diff):
        parser.error(tr(lang, "err_write_conflict"))

    if args.config_template:
        formatting = (
            args.paths
            or args.write
            or args.check
            or args.diff
            or args.lines
            or args.line_width is not None
            or args.base_indent is not None
            or args.stdin_path
            or args.only is not None
            or args.skip is not None
            or args.config is not None
            or args.strict
            or args.best_effort
        )
        if formatting:
            parser.error(tr(lang, "err_config_template_conflict"))
        sys.stdout.write(render_template(lang))
        return 0

    stdin_mode = not args.paths or args.paths == ["-"]
    if "-" in args.paths and len(args.paths) > 1:
        parser.error(tr(lang, "err_dash_mixed"))
    if args.stdin_path and not stdin_mode:
        parser.error(tr(lang, "err_stdin_path"))
    if args.write and stdin_mode:
        parser.error(tr(lang, "err_write_stdin"))
    if args.lines and len(args.paths) > 1:
        parser.error(tr(lang, "err_lines_one_file"))
    if args.lines and any(Path(raw).is_dir() for raw in args.paths):
        parser.error(tr(lang, "err_lines_one_file"))

    scan_failed = False
    paths: list[Path] = []
    if not stdin_mode:
        paths, scan_failed = _expand_inputs(args.paths, lang)
        if not paths and scan_failed:
            return 2
        if args.lines and len(paths) != 1:
            parser.error(tr(lang, "err_lines_one_file"))
        if not (args.write or args.check or args.diff) and len(paths) != 1:
            parser.error(tr(lang, "err_multiple_need_action"))

    start = Path(args.stdin_path).parent if args.stdin_path else Path.cwd()
    try:
        options = load_config(args.config, start)
    except ConfigError as exc:
        print(f"skillfmt: {exc}", file=sys.stderr)
        return 2
    if args.verbose:
        if options.config_path:
            print(tr(lang, "verbose_config").format(path=options.config_path), file=sys.stderr)
        else:
            print(tr(lang, "verbose_no_config"), file=sys.stderr)

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
        _print_warnings("stdin", result.warnings, args.quiet, lang)
        if args.diff:
            diff = _diff("stdin", text, result.text)
            _print_verbose(args, "stdin", result.text != text, lang)
            if diff:
                sys.stdout.write(diff)
                return 1
            return 0
        if args.check:
            _print_verbose(args, "stdin", result.text != text, lang)
            if result.text != text:
                print("stdin: " + tr(lang, "would_reformat"))
                return 1
            return 0
        sys.stdout.write(result.text)
        _print_verbose(args, "stdin", result.text != text, lang)
        return 0

    failures = 1 if scan_failed else 0
    changed = 0
    for path in paths:
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
        _print_warnings(str(path), result.warnings, args.quiet, lang)
        if result.text == text:
            _print_verbose(args, str(path), False, lang)
            continue
        changed += 1
        if args.write:
            try:
                _write_atomic(path, result.text)
            except OSError as exc:
                print(f"{path}: {exc}", file=sys.stderr)
                failures = 1
                continue
        elif args.diff:
            sys.stdout.write(_diff(str(path), text, result.text))
        elif args.check:
            print(f"{path}: {tr(lang, 'would_reformat')}")
        else:
            sys.stdout.write(result.text)
        _print_verbose(args, str(path), True, lang)

    if failures:
        return 2
    if (args.check or args.diff) and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
