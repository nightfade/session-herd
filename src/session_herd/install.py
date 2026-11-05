"""`herd install` / `herd uninstall`: wire the state hook and skills into Claude Code and Codex."""

import json
import shlex
import shutil
import sys
import time
import tomllib
from pathlib import Path

from session_herd.paths import CLAUDE_HOME, CODEX_HOME

MARKER = "session_herd.hook"
CLAUDE_EVENTS = [
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Notification",  # permission_prompt = a dialog is on screen (see hook.classify)
    "Stop",
    "StopFailure",
    "SessionEnd",
]
CODEX_EVENTS = [
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PermissionRequest",
    "Stop",
    "SessionEnd",
]
SKILLS_DIR = Path(__file__).parent / "skills"


def hook_command(tool, python=None):
    # `|| true`: a hook that exits 2 makes Claude Code block the user's prompt.
    return f"{shlex.quote(python or sys.executable)} -m {MARKER} {tool} 2>/dev/null || true"


def strip_hooks(hooks):
    """Remove our entries (and matcher groups left empty) from a hooks mapping, in place."""
    for event in list(hooks):
        groups = []
        for g in hooks[event]:
            kept = [h for h in g.get("hooks", []) if MARKER not in h.get("command", "")]
            if kept:
                groups.append({**g, "hooks": kept})
            elif not g.get("hooks"):
                groups.append(g)
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]


def add_hooks(hooks, events, command):
    for event in events:
        hooks.setdefault(event, []).append({"hooks": [{"type": "command", "command": command, "timeout": 5}]})


def _rewrite(path, change):
    data = json.loads(path.read_text()) if path.exists() else {}
    if path.exists():
        shutil.copy2(path, path.with_name(f"{path.name}.bak-herd-{time.strftime('%Y%m%d%H%M%S')}"))
    change(data.setdefault("hooks", {}))
    if not data["hooks"]:
        del data["hooks"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _targets():
    out = []
    if CLAUDE_HOME.exists():
        out.append(("claude", CLAUDE_HOME / "settings.json", CLAUDE_EVENTS, CLAUDE_HOME / "skills"))
    if CODEX_HOME.exists():
        out.append(("codex", CODEX_HOME / "hooks.json", CODEX_EVENTS, CODEX_HOME / "skills"))
    return out


def install():
    for tool, settings, events, skills in _targets():
        cmd = hook_command(tool)

        def change(hooks, events=events, cmd=cmd):
            strip_hooks(hooks)
            add_hooks(hooks, events, cmd)

        _rewrite(settings, change)
        print(f"{tool}: hooks -> {settings}")
        skills.mkdir(parents=True, exist_ok=True)
        for src in sorted(SKILLS_DIR.iterdir()):
            dst = skills / src.name
            if dst.is_symlink():
                dst.unlink()
            elif dst.exists():
                print(f"{tool}: skipped skill {src.name}: {dst} exists and is not a symlink")
                continue
            dst.symlink_to(src)
            print(f"{tool}: skill /{src.name} -> {dst}")
    _codex_hint()


def uninstall():
    for tool, settings, _, skills in _targets():
        if settings.exists():
            _rewrite(settings, strip_hooks)
            print(f"{tool}: removed hooks from {settings}")
        for src in SKILLS_DIR.iterdir():
            dst = skills / src.name
            if dst.is_symlink() and Path(dst.readlink()) == src:
                dst.unlink()
                print(f"{tool}: removed skill {dst}")


def _codex_hint():
    cfg = CODEX_HOME / "config.toml"
    if not CODEX_HOME.exists():
        return
    try:
        enabled = tomllib.loads(cfg.read_text()).get("features", {}).get("hooks")
    except (OSError, ValueError):
        enabled = None
    if not enabled:
        print("codex: hooks only run with `[features] hooks = true` in ~/.codex/config.toml")
    print("codex: approve the new hooks when Codex asks on its next start")
