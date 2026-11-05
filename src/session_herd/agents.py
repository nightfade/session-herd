"""Agent-side facts: which process runs on which tty, Claude's session registry, transcripts."""

import json
import re
import shlex
import subprocess

from session_herd.paths import CLAUDE_HOME, CODEX_HOME, STATE_DIR


def agents_by_tty(claude_reg):
    """tty -> (tool, pid) for the agent running in each terminal.

    Launchers and wrappers often share the tty with the real agent, so for
    Claude prefer the pid that has a record in Claude's session registry.
    """
    out = subprocess.run(["ps", "-axo", "pid=,tty=,command="], capture_output=True, text=True).stdout
    found = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or parts[1] in ("??", "-"):
            continue
        pid, tty = int(parts[0]), "/dev/" + parts[1]
        name = parts[2].split()[0].rsplit("/", 1)[-1]
        if name == "claude":
            found.setdefault(tty, {}).setdefault("claude", []).append(pid)
        elif re.fullmatch(r"codex[\w.-]*", name):
            found.setdefault(tty, {}).setdefault("codex", []).append(pid)
    agents = {}
    for tty, tools in found.items():
        if "claude" in tools:
            pids = tools["claude"]
            agents[tty] = ("claude", next((p for p in pids if p in claude_reg), pids[-1]))
        else:
            agents[tty] = ("codex", tools["codex"][-1])
    return agents


def claude_registry():
    """pid -> Claude Code's own session record (~/.claude/sessions/<pid>.json)."""
    reg = {}
    for f in (CLAUDE_HOME / "sessions").glob("*.json"):
        try:
            d = json.loads(f.read_text())
            reg[d["pid"]] = d
        except (OSError, ValueError, KeyError):
            pass
    return reg


def hook_states():
    """terminal id -> newest hook record for that terminal session."""
    by_terminal = {}
    for f in STATE_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        d["_file"] = str(f)
        prev = by_terminal.get(d.get("terminal"))
        if prev is None or d.get("updated", 0) > prev.get("updated", 0):
            by_terminal[d.get("terminal")] = d
    return by_terminal


def prune_states(live_terminals):
    for f in STATE_DIR.glob("*.json"):
        try:
            if json.loads(f.read_text()).get("terminal") not in live_terminals:
                f.unlink()
        except (OSError, ValueError):
            pass


def find_transcript(tool, sid):
    if not sid:
        return ""
    if tool == "claude":
        hits = list((CLAUDE_HOME / "projects").glob(f"*/{sid}.jsonl"))
    else:
        hits = list((CODEX_HOME / "sessions").glob(f"*/*/*/rollout-*{sid}.jsonl"))
    return str(hits[0]) if hits else ""


def _tail_lines(path, nbytes=400_000):
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - nbytes))
        data = f.read().decode("utf-8", "ignore")
    lines = data.splitlines()
    return lines[1:] if size > nbytes else lines


def _text(content, kinds):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") in kinds)


def parse_turn(tool, d):
    """One transcript line -> ("user" | "agent", text) or None. Skips tool traffic and injected context."""
    if tool == "claude":
        if d.get("isMeta") or d.get("type") not in ("user", "assistant"):
            return None
        content = (d.get("message") or {}).get("content", "")
        if d["type"] == "user" and isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        ):
            return None
        role, text = ("user" if d["type"] == "user" else "agent"), _text(content, {"text"})
    else:
        p = d.get("payload") or {}
        item = p.get("item") or {}
        if p.get("type") == "item_completed" and item.get("type") == "UserMessage":
            role, text = "user", _text(item.get("content", []), {"text"})
        elif p.get("type") == "message" and p.get("role") == "assistant":
            role, text = "agent", _text(p.get("content", []), {"output_text"})
        else:
            return None
    text = text.strip()
    if not text or text.startswith("<"):
        return None
    return role, text


def recent_turns(tool, path, n):
    turns = []
    for line in _tail_lines(path):
        try:
            turn = parse_turn(tool, json.loads(line))
        except ValueError:
            continue
        if turn:
            turns.append(turn)
    return turns[-n:]


def launch_command(cfg, key, thread, prompt):
    """Shell line that starts the topic's agent from the root directory.

    Always start from root, never from the topic's own dir: project instructions
    (CLAUDE.md / AGENTS.md) and per-directory memory are found from the launch
    directory, and sandboxed launchers scope file access to it.
    """
    t = cfg.topics[key]
    tool = t.get("tool", "claude")
    label = t.get("label", key) + (f"·{thread}" if thread else "")
    env = f"HERD_TOPIC={shlex.quote(key)}"
    if thread:
        env += f" HERD_THREAD={shlex.quote(thread)}"
    cmd = cfg.agent_command(key)
    if tool == "claude":
        cmd += f" --name {shlex.quote(label)}"
    return f"cd {shlex.quote(str(cfg.root))} && {env} {cmd} {shlex.quote(prompt)}"


def pid_alive(pid):
    return subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0
