from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vim74_static_compatibility() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "editors" / "check_vim74.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_vscode_manifest_declares_skill_without_file_associations() -> None:
    manifest = json.loads(
        (ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8")
    )
    contributes = manifest["contributes"]
    languages = contributes["languages"]
    assert manifest["name"] == "skfmt"
    assert manifest["publisher"] == "YEUNGCHIE"
    assert manifest["activationEvents"] == ["onStartupFinished"]
    assert len(languages) == 1
    assert languages[0]["id"] == "skill"
    assert "extensions" not in languages[0]
    assert "configurationDefaults" not in contributes
    assert "skfmt.languages" not in contributes["configuration"]["properties"]
    assert ".il" not in json.dumps(contributes)
    assert ".ils" not in json.dumps(contributes)
    assert (ROOT / "editors" / "vscode" / "language-configuration.json").is_file()


def test_vim_headless_smoke() -> None:
    vim = shutil.which("vim")
    if vim is None:
        return
    result = subprocess.run(
        [vim, "-Nu", "NONE", "-es", "-S", "tests/editors/vim_test.vim"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
