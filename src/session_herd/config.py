"""Topic registry: ~/.config/session-herd/topics.toml (or $SESSION_HERD_CONFIG)."""

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from session_herd.paths import CONFIG_FILE

COLORS = {
    "red": (220, 80, 80),
    "orange": (230, 140, 50),
    "yellow": (220, 190, 60),
    "green": (90, 170, 90),
    "teal": (60, 160, 160),
    "blue": (80, 130, 220),
    "purple": (150, 100, 200),
    "pink": (220, 110, 170),
    "gray": (140, 140, 140),
}

KEY_RE = re.compile(r"[a-z][a-z0-9_-]*")

DEFAULTS = {
    "root": "~",
    "language": "en",
    "claude": "claude",
    "codex": "codex",
    "handoff_heading": "",
}


@dataclass
class Config:
    defaults: dict
    topics: dict = field(default_factory=dict)
    manager: dict = field(default_factory=dict)
    path: Path = CONFIG_FILE

    @property
    def root(self):
        return Path(os.path.expanduser(self.defaults["root"]))

    @property
    def language(self):
        return self.defaults["language"]

    def resolve(self, p):
        """Path relative to root (or absolute). No resolve(): realpath on $HOME is denied in some sandboxes."""
        if not p:
            return None
        return Path(os.path.normpath(self.root / os.path.expanduser(p)))

    def topic_for_cwd(self, cwd):
        """The topic whose `dir` contains cwd (longest match). The root itself belongs to no topic."""
        best, best_len = "", 0
        for key, t in self.topics.items():
            d = str(self.resolve(t.get("dir", ".")))
            if d == str(self.root):
                continue
            if (cwd == d or cwd.startswith(d + "/")) and len(d) > best_len:
                best, best_len = key, len(d)
        return best

    def handoff_file(self, key):
        t = self.topics.get(key, {})
        return self.resolve(t.get("handoff") or t.get("entry"))


def load(path=None):
    path = Path(path or CONFIG_FILE)
    raw = tomllib.loads(path.read_text()) if path.exists() else {}
    return Config(
        defaults={**DEFAULTS, **raw.get("defaults", {})},
        topics=raw.get("topics", {}),
        manager=raw.get("manager", {}),
        path=path,
    )


def topic_block(key, label, dir, scope, kind, tool, color, entry=None, private=False):
    if not KEY_RE.fullmatch(key):
        raise ValueError("topic key must match [a-z][a-z0-9_-]*")
    lines = [
        f"[topics.{key}]",
        f"label = {_q(label)}",
        f"scope = {_q(scope)}",
        f"kind = {_q(kind)}",
        f"dir = {_q(dir)}",
    ]
    if entry:
        lines.append(f"entry = {_q(entry)}")
    lines += [f"tool = {_q(tool)}", f"color = {_q(color)}"]
    if private:
        lines.append("private = true")
    return "\n".join(lines) + "\n"


def _q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
