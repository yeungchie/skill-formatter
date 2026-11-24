from __future__ import annotations

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
