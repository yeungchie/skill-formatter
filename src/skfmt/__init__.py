"""Public API for the SKILL formatter."""

from .formatter import FormatResult, format_range, format_source
from .identity import CONFIG_NAME, DIST_NAME, LANG_ENV, TOOL_NAME
from .options import CATEGORIES, Options

__version__ = "0.1.0"

__all__ = [
    "CATEGORIES",
    "CONFIG_NAME",
    "DIST_NAME",
    "LANG_ENV",
    "Options",
    "FormatResult",
    "TOOL_NAME",
    "format_range",
    "format_source",
]
