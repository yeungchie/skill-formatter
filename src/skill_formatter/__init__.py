"""Public API for the SKILL formatter."""

from .formatter import FormatResult, format_range, format_source
from .options import CATEGORIES, Options

__version__ = "0.1.0"

__all__ = ["CATEGORIES", "Options", "FormatResult", "format_range", "format_source"]
