import json
import tomllib
from pathlib import Path

import pytest

from session_herd import agents, config, hook, install

EXAMPLE = Path(__file__).parent.parent / "examples" / "topics.toml"


# ---------- hook ----------


@pytest.mark.parametrize(
    "event,data,expected",
    [
        ("UserPromptSubmit", {}, "working"),
        ("PreToolUse", {}, "working"),
        ("Stop", {}, "idle"),
        ("SessionStart", {}, "idle"),
        ("PermissionRequest", {}, "waiting"),
        ("Notification", {"notification_type": "permission_prompt"}, "waiting"),
        ("Notification", {"notification_type": "idle_prompt"}, "idle"),
        ("Notification", {"message": "Claude is waiting for your input"}, "idle"),
        ("SubagentStop", {}, None),
    ],
)
def test_classify(event, data, expected):
    assert hook.classify(event, data) == expected


def test_record_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "STATE_DIR", tmp_path)
    env = {"ITERM_SESSION_ID": "w0t1p0:ABC-123", "HERD_TOPIC": "invest"}
    hook.record("claude", {"session_id": "s1", "hook_event_name": "PermissionRequest", "cwd": "/x"}, env, now=10)
    rec = json.loads((tmp_path / "claude-s1.json").read_text())
    assert rec["state"] == "waiting" and rec["terminal"] == "ABC-123" and rec["topic"] == "invest"
    assert rec["since"] == 10

    # same state keeps its start time; the topic survives an env without HERD_TOPIC
    hook.record("claude", {"session_id": "s1", "hook_event_name": "Notification"}, {}, now=20)
    rec = json.loads((tmp_path / "claude-s1.json").read_text())
    assert rec["since"] == 10 and rec["topic"] == "invest" and rec["terminal"] == "ABC-123"

    hook.record("claude", {"session_id": "s1", "hook_event_name": "UserPromptSubmit"}, {}, now=30)
    rec = json.loads((tmp_path / "claude-s1.json").read_text())
    assert rec["state"] == "working" and rec["last_prompt"] == 30

    hook.record("claude", {"session_id": "s1", "hook_event_name": "SessionEnd"}, {})
    assert not (tmp_path / "claude-s1.json").exists()


def test_main_never_raises(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("not json"))
    hook.main()
    assert capsys.readouterr().out == ""


# ---------- config ----------


def test_example_config_loads():
    cfg = config.load(EXAMPLE)
    assert cfg.language == "en"
    assert cfg.topics["journal"]["private"] is True
    assert cfg.resolve("notes/x.md") == cfg.root / "notes/x.md"
    assert cfg.handoff_file("api") == cfg.root / "services/api/HANDOFF.md"
    assert cfg.handoff_file("invest") == cfg.root / "notes/investing/README.md"


def test_topic_for_cwd_longest_match_and_root_excluded():
    cfg = config.load(EXAMPLE)
    root = str(cfg.root)
    assert cfg.topic_for_cwd(root + "/services/api/src") == "api"
    assert cfg.topic_for_cwd(root) == ""  # the herd topic's dir is root itself
    assert cfg.topic_for_cwd(root + "/services/apix") == ""


def test_topic_block_round_trips():
    block = config.topic_block("garden", 'My "garden"', "notes/garden", "personal", "think", "claude", "green", private=True)
    t = tomllib.loads(block)["topics"]["garden"]
    assert t["label"] == 'My "garden"' and t["private"] is True
    with pytest.raises(ValueError):
        config.topic_block("Bad Key", "x", ".", "p", "think", "claude", "gray")


# ---------- agents ----------


def test_parse_turn_claude():
    assert agents.parse_turn("claude", {"type": "user", "message": {"content": "hello"}}) == ("user", "hello")
    tool_result = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}
    assert agents.parse_turn("claude", tool_result) is None
    injected = {"type": "user", "message": {"content": "<command-name>/clear</command-name>"}}
    assert agents.parse_turn("claude", injected) is None
    reply = {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}, {"type": "tool_use"}]}}
    assert agents.parse_turn("claude", reply) == ("agent", "done")


def test_parse_turn_codex():
    user = {"payload": {"type": "item_completed", "item": {"type": "UserMessage", "content": [{"type": "text", "text": "hi"}]}}}
    assert agents.parse_turn("codex", user) == ("user", "hi")
    reply = {"payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}}
    assert agents.parse_turn("codex", reply) == ("agent", "ok")
    assert agents.parse_turn("codex", {"payload": {"type": "reasoning"}}) is None


def test_launch_command_starts_from_root():
    cfg = config.load(EXAMPLE)
    cmd = agents.launch_command(cfg, "invest", "q4", "read the doc")
    assert cmd.startswith(f"cd {cfg.root} && HERD_TOPIC=invest HERD_THREAD=q4 claude --name")
    assert "Investing·q4" in cmd
    assert "--name" not in agents.launch_command(cfg, "api", "", "go")  # codex has no --name


# ---------- install ----------


def test_hook_merge_is_idempotent_and_keeps_foreign_hooks():
    foreign = {"type": "command", "command": "other-tool"}
    hooks = {"Stop": [{"hooks": [foreign]}], "PreToolUse": [{"matcher": "Bash", "hooks": [foreign]}]}
    cmd = install.hook_command("claude", python="/py")
    for _ in range(2):
        install.strip_hooks(hooks)
        install.add_hooks(hooks, install.CLAUDE_EVENTS, cmd)
    ours = [h for groups in hooks.values() for g in groups for h in g["hooks"] if install.MARKER in h["command"]]
    assert len(ours) == len(install.CLAUDE_EVENTS)
    assert cmd.endswith("|| true")

    install.strip_hooks(hooks)
    assert hooks == {"Stop": [{"hooks": [foreign]}], "PreToolUse": [{"matcher": "Bash", "hooks": [foreign]}]}


def test_every_message_formats_in_every_language():
    import string

    from session_herd.i18n import MESSAGES, msg

    assert set(MESSAGES["zh"]) == set(MESSAGES["en"])
    for lang, table in MESSAGES.items():
        for msgid, text in table.items():
            fields = {f for _, f, _, _ in string.Formatter().parse(text) if f}
            msg(lang, msgid, **{f: "x" for f in fields})  # e.g. a {key} placeholder must not clash
