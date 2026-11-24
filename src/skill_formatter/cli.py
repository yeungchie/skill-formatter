"""Command line interface for skill-formatter."""

from __future__ import annotations

import argparse
import difflib
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn, cast

from rich.console import Console
from rich.syntax import Syntax
from rich_argparse import RawDescriptionRichHelpFormatter

from . import __version__
from .config import (
    ConfigError,
    config_key_spec,
    config_option_value,
    find_config,
    format_config_value,
    load_config,
    render_template,
    set_config_text,
)
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
            super().add_usage(
                usage,
                actions,
                groups,
                prefix=strings["usage"] if prefix is None else prefix,
            )

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

    def add_help_option(target: argparse.ArgumentParser) -> None:
        target.add_argument("-h", "--help", action="help", help=strings["help"])

    def add_language_options(
        target: argparse.ArgumentParser, *, suppress_default: bool = False
    ) -> None:
        default = argparse.SUPPRESS if suppress_default else False
        language = target.add_mutually_exclusive_group()
        language.add_argument(
            "--zh", action="store_true", default=default, help=strings["force_zh"]
        )
        language.add_argument(
            "--en", action="store_true", default=default, help=strings["force_en"]
        )

    def set_titles(target: argparse.ArgumentParser, positional: str) -> None:
        target._positionals.title = positional
        target._optionals.title = strings["options"]

    common = LocalizedParser(add_help=False)
    common.add_argument("paths", nargs="*", metavar="PATH", help=strings["paths"])
    common.add_argument(
        "--lines",
        action="append",
        type=parse_line_range,
        metavar="A:B",
        help=strings["lines"],
    )
    common.add_argument(
        "--line-width",
        type=parse_width,
        dest="line_width",
        metavar="N",
        help=strings["line_width"],
    )
    common.add_argument("--base-indent", type=int, metavar="N", help=strings["base_indent"])
    common.add_argument("--stdin-path", metavar="PATH", help=strings["stdin_path"])
    common.add_argument("--only", type=parse_categories, metavar="CATS", help=strings["only"])
    common.add_argument("--skip", type=parse_categories, metavar="CATS", help=strings["skip"])
    common.add_argument("--config", type=Path, metavar="PATH", help=strings["config"])
    common.add_argument("--strict", action="store_true", help=strings["strict"])
    common.add_argument("--best-effort", action="store_true", help=strings["best_effort"])
    common.add_argument("-q", "--quiet", action="store_true", help=strings["quiet"])
    common.add_argument("-v", "--verbose", action="store_true", help=strings["verbose"])

    parser = LocalizedParser(
        prog="skill-formatter",
        description=strings["description"],
        formatter_class=LocalizedFormatter,
        add_help=False,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"skill-formatter {__version__}",
        help=strings["version"],
    )
    add_help_option(parser)
    add_language_options(parser)
    set_titles(parser, strings["commands"])

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title=strings["commands"],
    )

    format_parser = subparsers.add_parser(
        "format",
        parents=[common],
        add_help=False,
        help=strings["command_format"],
        description=strings["format_description"],
        formatter_class=LocalizedFormatter,
    )
    set_titles(format_parser, strings["positional"])
    format_parser.add_argument("-w", "--write", action="store_true", help=strings["write"])
    add_language_options(format_parser, suppress_default=True)
    add_help_option(format_parser)

    for name, command_help, description in (
        ("check", strings["command_check"], strings["check_description"]),
        ("diff", strings["command_diff"], strings["diff_description"]),
    ):
        sub = subparsers.add_parser(
            name,
            parents=[common],
            add_help=False,
            help=command_help,
            description=description,
            formatter_class=LocalizedFormatter,
        )
        set_titles(sub, strings["positional"])
        add_language_options(sub, suppress_default=True)
        add_help_option(sub)

    config_parser = subparsers.add_parser(
        "config",
        add_help=False,
        help=strings["command_config"],
        description=strings["config_description"],
        formatter_class=LocalizedFormatter,
    )
    set_titles(config_parser, strings["commands"])
    add_language_options(config_parser, suppress_default=True)
    add_help_option(config_parser)
    config_sub = config_parser.add_subparsers(
        dest="config_command",
        required=True,
        title=strings["commands"],
    )

    def add_config_leaf(
        name: str,
        help_text: str,
        description: str,
        *,
        with_config: bool = True,
    ) -> argparse.ArgumentParser:
        leaf = config_sub.add_parser(
            name,
            add_help=False,
            help=help_text,
            description=description,
            formatter_class=LocalizedFormatter,
        )
        set_titles(leaf, strings["positional"])
        if with_config:
            leaf.add_argument(
                "--config",
                type=Path,
                metavar="PATH",
                default=argparse.SUPPRESS,
                help=strings["config_file"],
            )
        add_language_options(leaf, suppress_default=True)
        add_help_option(leaf)
        return leaf

    add_config_leaf(
        "template",
        strings["config_template"],
        strings["config_template"],
        with_config=False,
    )
    get_parser = add_config_leaf("get", strings["config_get"], strings["config_get"])
    get_parser.add_argument("key", metavar="KEY", help=strings["config_key"])
    set_parser = add_config_leaf("set", strings["config_set"], strings["config_set"])
    set_parser.add_argument("key", metavar="KEY", help=strings["config_key"])
    set_parser.add_argument("value", metavar="VALUE", help=strings["config_value"])
    add_config_leaf("trace", strings["config_trace"], strings["config_trace"])

    return parser


def _apply_cli_options(args: argparse.Namespace, options: Options) -> Options:
    cats = set(options.categories)
    if args.only is not None:
        cats = set(args.only)
        if "wrapping" in cats:
            cats.update({"indent", "spacing", "comments"})
        if "comments" in cats:
            cats.add("indent")
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
        config_path=options.config_path,
        warnings=list(options.warnings),
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
            config_path=opts.config_path,
            warnings=list(opts.warnings),
        )
    return format_source(text, opts)


def _write_atomic(path: Path, text: str) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".skill-formatter-", dir=directory)
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


def _read_stdin() -> bytes:
    """Read stdin until EOF; POSIX ttys send EOF with Ctrl+D."""
    try:
        return sys.stdin.buffer.read()
    except (OSError, ValueError):
        return b""


def _diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=path,
            tofile=path + " (formatted)",
        )
    )


def _active_config_path(raw: Path | None, cwd: Path, create: bool) -> Path | None:
    if raw is not None:
        if not create and not raw.is_file():
            raise ConfigError(f"cannot read {raw}")
        return raw
    found = find_config(cwd)
    if found is not None:
        return found
    return cwd / "skill-formatter.toml" if create else None


def _print_config_template(lang: str) -> None:
    console = Console(soft_wrap=True)
    console.print(
        Syntax(
            render_template(lang).rstrip("\n"),
            "toml",
            theme="ansi_dark",
            line_numbers=False,
            word_wrap=False,
            background_color=None,
        ),
        end="",
    )


def _run_config(args: argparse.Namespace, lang: str) -> int:
    command = args.config_command
    if command == "template":
        _print_config_template(lang)
        return 0
    cwd = Path.cwd()
    raw_config = getattr(args, "config", None)
    try:
        if command == "get":
            spec = config_key_spec(args.key)
            path = _active_config_path(raw_config, cwd, create=False)
            options = load_config(path, cwd)
            print(format_config_value(config_option_value(options, args.key), spec))
            return 0
        if command == "trace":
            path = _active_config_path(raw_config, cwd, create=False)
            if path is not None:
                print(path.resolve())
            return 0
        if command == "set":
            path = _active_config_path(raw_config, cwd, create=True)
            if path is None:
                raise ConfigError("cannot determine configuration file")
            old = path.read_text(encoding="utf-8") if path.is_file() else ""
            _write_atomic(path, set_config_text(old, args.key, args.value))
            print(tr(lang, "config_updated").format(path=path.resolve()))
            return 0
    except (ConfigError, OSError) as exc:
        print(f"skill-formatter: {exc}", file=sys.stderr)
        return 2
    return 2


def _prescan_language(argv: list[str]) -> str | None:
    for arg in argv:
        if arg == "--":
            break
        if arg == "--zh":
            return "zh"
        if arg == "--en":
            return "en"
    return None


def _main(arguments: list[str]) -> int:
    parser = build_parser(_prescan_language(arguments))
    args = parser.parse_args(arguments)
    lang = "zh" if args.zh else "en" if args.en else detect_language()
    if args.zh and args.en:
        parser.error(tr(lang, "err_language_flags"))
    if args.command == "config":
        return _run_config(args, lang)

    write = getattr(args, "write", False)
    if args.only is not None and args.skip is not None:
        parser.error(tr(lang, "err_only_skip"))
    if args.strict and args.best_effort:
        parser.error(tr(lang, "err_strict_best_effort"))
    if args.quiet and args.verbose:
        parser.error(tr(lang, "err_quiet_verbose"))

    stdin_mode = not args.paths or args.paths == ["-"]
    if "-" in args.paths and len(args.paths) > 1:
        parser.error(tr(lang, "err_dash_mixed"))
    if args.stdin_path and not stdin_mode:
        parser.error(tr(lang, "err_stdin_path"))
    if write and stdin_mode:
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
        if args.command == "format" and not write and len(paths) != 1:
            parser.error(tr(lang, "err_multiple_need_action"))

    start = Path(args.stdin_path).parent if args.stdin_path else Path.cwd()
    try:
        options = load_config(args.config, start)
    except ConfigError as exc:
        print(f"skill-formatter: {exc}", file=sys.stderr)
        return 2
    if args.verbose:
        if options.config_path:
            print(tr(lang, "verbose_config").format(path=options.config_path), file=sys.stderr)
        else:
            print(tr(lang, "verbose_no_config"), file=sys.stderr)

    if stdin_mode:
        raw = _read_stdin()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            print(f"stdin: {exc}", file=sys.stderr)
            if args.command == "format":
                sys.stdout.buffer.write(raw)
            return 2
        try:
            result = _format_text(text, args, options)
        except FormatError as exc:
            print(f"stdin: {exc}", file=sys.stderr)
            if args.command == "format":
                sys.stdout.buffer.write(raw)
            return 2
        _print_warnings("stdin", result.warnings, args.quiet, lang)
        if args.command == "diff":
            diff = _diff("stdin", text, result.text)
            _print_verbose(args, "stdin", result.text != text, lang)
            if diff:
                sys.stdout.write(diff)
                return 1
            return 0
        if args.command == "check":
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
        if args.command == "format" and write:
            try:
                _write_atomic(path, result.text)
            except OSError as exc:
                print(f"{path}: {exc}", file=sys.stderr)
                failures = 1
                continue
        elif args.command == "diff":
            sys.stdout.write(_diff(str(path), text, result.text))
        elif args.command == "check":
            print(f"{path}: {tr(lang, 'would_reformat')}")
        else:
            sys.stdout.write(result.text)
        _print_verbose(args, str(path), True, lang)

    if failures:
        return 2
    if args.command in {"check", "diff"} and changed:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdio()
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        return _main(arguments)
    except KeyboardInterrupt:
        lang = _prescan_language(arguments) or detect_language()
        print(f"skill-formatter: {tr(lang, 'interrupted')}", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
