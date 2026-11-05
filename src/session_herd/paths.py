"""Filesystem locations. Standard library only: the hook imports this on every agent event."""

import os
from pathlib import Path


def _xdg(var, default):
    return Path(os.environ.get(var) or Path.home() / default)


CONFIG_FILE = Path(
    os.environ.get("SESSION_HERD_CONFIG")
    or _xdg("XDG_CONFIG_HOME", ".config") / "session-herd" / "topics.toml"
)
STATE_DIR = _xdg("XDG_CACHE_HOME", ".cache") / "session-herd" / "state"

CLAUDE_HOME = Path.home() / ".claude"
CODEX_HOME = Path.home() / ".codex"
