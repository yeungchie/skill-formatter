"""Optional rich-based presentation helpers.

``skfmt`` must stay usable from a plain source checkout on machines where no
third-party package can be installed.  Rich is therefore imported lazily and
every caller has a plain-text fallback.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from .identity import TOOL_NAME

PLAIN_ENV = f"{TOOL_NAME.upper()}_PLAIN"

RICH_AVAILABLE = False
Console: Any = None
Syntax: Any = None
RawDescriptionRichHelpFormatter: Any = argparse.RawDescriptionHelpFormatter

if not os.environ.get(PLAIN_ENV, "").strip():
    try:
        from rich.console import Console as _Console
        from rich.syntax import Syntax as _Syntax
        from rich_argparse import RawDescriptionRichHelpFormatter as _RichFormatter
    except ImportError:
        pass
    else:
        Console = _Console
        Syntax = _Syntax
        RawDescriptionRichHelpFormatter = _RichFormatter
        RICH_AVAILABLE = True
