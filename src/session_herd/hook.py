"""Lifecycle hook for Claude Code and Codex: record each session's state.

Installed by `herd install` as `<python> -m session_herd.hook claude|codex`.
Standard library only, prints nothing, and never fails: some agents treat a
hook's stdout as model context, and Claude Code treats exit code 2 as "block
this prompt", so a crashing hook would swallow the user's input.
"""

import json
import os
import sys
import time

from session_herd.paths import STATE_DIR

WORKING = {"UserPromptSubmit", "PreToolUse", "PostToolUse"}
IDLE = {"SessionStart", "Stop", "StopFailure", "Interrupt"}


def classify(event, data):
    """Map a hook event to waiting / idle / working, or None to ignore it.

    PermissionRequest is only installed for Codex: Claude Code fires it before
    deciding, including for requests auto mode approves, so for Claude the
    permission_prompt Notification is the signal that a dialog is on screen.
    """
    if event in WORKING:
        return "working"
    if event in IDLE:
        return "idle"
    if event == "PermissionRequest":
        return "waiting"
    if event == "Notification":
        # The 60-second "still waiting for your input" nudge is not a permission prompt.
        kind = data.get("notification_type") or ""
        msg = (data.get("message") or "").lower()
        if kind == "idle_prompt" or "waiting for your input" in msg:
            return "idle"
        return "waiting"
    return None


def record(tool, data, env=os.environ, now=None):
    sid = data.get("session_id") or data.get("thread_id")
    event = data.get("hook_event_name") or ""
    if not sid:
        return
    path = STATE_DIR / f"{tool}-{sid}.json"
    if event == "SessionEnd":
        path.unlink(missing_ok=True)
        return
    state = classify(event, data)
    if state is None:
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        rec = json.loads(path.read_text())
    except (OSError, ValueError):
        rec = {}
    now = now or time.time()
    terminal = env.get("ITERM_SESSION_ID", "").split(":", 1)[-1] or env.get("TMUX_PANE", "")
    rec.update(
        tool=tool,
        session_id=sid,
        cwd=data.get("cwd") or rec.get("cwd", ""),
        transcript=data.get("transcript_path") or rec.get("transcript", ""),
        terminal=terminal or rec.get("terminal", ""),
        topic=env.get("HERD_TOPIC") or rec.get("topic", ""),
        thread=env.get("HERD_THREAD") or rec.get("thread", ""),
        event=event,
        updated=now,
    )
    if rec.get("state") != state:
        rec["state"] = state
        rec["since"] = now
    if event == "UserPromptSubmit":
        rec["last_prompt"] = now
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False))
    tmp.replace(path)


def main():
    try:
        record(sys.argv[1] if len(sys.argv) > 1 else "claude", json.load(sys.stdin))
    except Exception:
        pass


if __name__ == "__main__":
    main()
