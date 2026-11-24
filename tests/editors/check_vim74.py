"""Static guard against Vim 8+ APIs in editors/vim."""

from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED = [
    r"\bsystemlist\s*\(",
    r"\bjob_start\s*\(",
    r"\bjob_stop\s*\(",
    r"\btimer_start\s*\(",
    r"\bjson_decode\s*\(",
    r"\bjson_encode\s*\(",
    r"\bdeletebufline\s*\(",
    r"\bgetbufinfo\s*\(",
    r"\bexecute\s*\(",
    r"\bpopup_\w+",
    r"\bnvim_\w+",
    r"->",
    r"\{[^}]*->",
    r":scriptversion\b",
    r":def\b",
    r":terminal\b",
]


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "editors" / "vim"
    failures = 0
    for path in sorted(root.rglob("*.vim")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith('"'):
                continue
            for pattern in BANNED:
                if re.search(pattern, line):
                    print(f"{path}:{number}: banned Vim 8+ construct {pattern}")
                    failures = 1
    if failures:
        return 1
    print("OK: Vim 7.4 compatibility scan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
