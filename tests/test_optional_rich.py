from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCK_RICH = """\
import sys

class BlockRich:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rich" or fullname.startswith("rich.") or fullname == "rich_argparse":
            raise ImportError("blocked for test")
        return None

sys.meta_path.insert(0, BlockRich())
sys.path.insert(0, {src!r})
from skfmt.cli import main
raise SystemExit(main(sys.argv[1:]))
"""


def run_without_rich(
    args: list[str],
    data: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    env.pop("SKFMT_PLAIN", None)
    script = BLOCK_RICH.format(src=str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, "-c", script, *args],
        input=data,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )


def test_cli_runs_without_rich() -> None:
    version = run_without_rich(["--version"])
    assert version.returncode == 0
    assert version.stdout.startswith("skfmt ")

    helped = run_without_rich(["--en", "-h"])
    assert helped.returncode == 0
    assert "Usage: skfmt" in helped.stdout

    template = run_without_rich(["--en", "config", "template"])
    assert template.returncode == 0
    assert "[format]" in template.stdout
    assert "width = 150" in template.stdout
    assert "\x1b[" not in template.stdout

    formatted = run_without_rich(["--en", "format"], "foo( 1 2 )\n")
    assert formatted.returncode == 0
    assert formatted.stdout == "foo(1 2)\n"


def test_plain_env_skips_rich() -> None:
    env = dict(os.environ)
    env["SKFMT_PLAIN"] = "1"
    env["NO_COLOR"] = "1"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from skfmt.ui import RICH_AVAILABLE; print(RICH_AVAILABLE)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "src")],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "False"
