from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from skill_formatter import __version__

ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def test_version_declarations_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    vscode = json.loads((ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
    assert vscode["version"] == __version__


def test_author_metadata_matches_publisher() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    vscode = json.loads((ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8"))
    assert pyproject["project"]["authors"] == [{"name": "YEUNGCHIE"}]
    assert vscode["publisher"] == "YEUNGCHIE"
    assert vscode["author"] == "YEUNGCHIE"
    assert "YEUNGCHIE" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "YEUNGCHIE" in (ROOT / "editors" / "vscode" / "LICENSE").read_text(encoding="utf-8")


def test_editors_require_available_cli_version() -> None:
    vscode = (ROOT / "editors" / "vscode" / "src" / "format.ts").read_text(encoding="utf-8")
    vim = (ROOT / "editors" / "vim" / "autoload" / "skillfmt.vim").read_text(encoding="utf-8")
    vscode_match = re.search(r'MIN_CLI_VERSION = "(\d+\.\d+\.\d+)"', vscode)
    vim_match = re.search(r"let s:min_version = '(\d+\.\d+\.\d+)'", vim)
    assert vscode_match is not None
    assert vim_match is not None
    minimum = vscode_match.group(1)
    assert vim_match.group(1) == minimum
    assert _version_tuple(__version__) >= _version_tuple(minimum)
