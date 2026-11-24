"""Single source of truth for the project's public names.

Keep the distribution name, console command, configuration file name and
language environment variable here.  A future rename then touches this module
and the packaging/editor manifests instead of the whole code base.
"""

from __future__ import annotations

TOOL_NAME = "skfmt"
DIST_NAME = TOOL_NAME
CONFIG_NAME = f"{TOOL_NAME}.toml"
LANG_ENV = f"{TOOL_NAME.upper()}_LANG"
