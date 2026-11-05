"""`herd` command line."""

import argparse
import json
import os
import sys
import time

from session_herd import agents, board, config, install
from session_herd.backends import get_backend
from session_herd.config import COLORS
from session_herd.i18n import msg
from session_herd.paths import STATE_DIR

HANDOFF_HEADINGS = {"en": "## Handoff", "zh": "## 当前交接"}


class Ctx:
    def __init__(self):
        self.cfg = config.load()
        self.lang = self.cfg.language
        self._backend = None

    def m(self, msgid, **kw):
        return msg(self.lang, msgid, **kw)

    @property
    def backend(self):
        if self._backend is None:
            self._backend = get_backend()
        return self._backend

    def rows(self):
        try:
            return board.collect(self.cfg, self.backend)
        except Exception as e:  # connection refused, API disabled, app not running
            sys.exit(self.m("backend_error", err=e))

    def one(self, ident):
        rows = self.rows()
        hits = board.resolve(rows, ident)
        if len(hits) != 1:
            names = ", ".join(f"{r.id}({r.topic or '?'})" for r in hits) or self.m("none")
            sys.exit(self.m("no_match", ident=ident, names=names))
        return hits[0]

    def state_label(self, state):
        return self.m(f"state.{state}")

    def name(self, r):
        return r.label or r.title[:24]


# ---------- board ----------


def cmd_status(ctx, args):
    rows = ctx.rows()
    if args.json:
        out = [r.as_dict() for r in rows]
        if not args.full:
            for r in out:
                r.pop("transcript")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    if not rows:
        print(ctx.m("no_sessions"))
        return
    for r in rows:
        name = (r.label or ctx.m("unclassified")) + (f"·{r.thread}" if r.thread else "")
        flags = (" 🔒" if r.private else "") + (f" {ctx.m('parked')}" if r.parked else "")
        print(
            f"{r.id}  {ctx.state_label(r.state):<9} {board.ago(r.since, ctx.lang):>7}  "
            f"{name}{flags}  [{r.tool}]  {r.title[:40]}"
        )


def cmd_tail(ctx, args):
    r = ctx.one(args.id)
    if r.private and not args.force:
        sys.exit(ctx.m("private_tail", label=r.label))
    if not r.transcript:
        sys.exit(ctx.m("no_transcript"))
    for role, text in agents.recent_turns(r.tool, r.transcript, args.n):
        if len(text) > args.width:
            text = text[: args.width] + " …"
        print(f"[{role}] {text}\n")


def cmd_focus(ctx, args):
    ctx.backend.focus(ctx.one(args.id).terminal)


def cmd_send(ctx, args):
    r = ctx.one(args.id)
    if r.private and not args.force:
        sys.exit(ctx.m("private_send", label=r.label))
    # Typing into a busy session mixes into whatever the user is typing, and at a
    # permission prompt the Enter would answer the prompt.
    if r.state != "idle" and not args.force:
        sys.exit(ctx.m("not_idle_send", id=r.id, state=ctx.state_label(r.state), idle=ctx.state_label("idle")))
    ctx.backend.send(r.terminal, args.text)
    print(ctx.m("sent", id=r.id, name=ctx.name(r)))


def cmd_wait(ctx, args):
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        r = ctx.one(args.id)
        if r.parked if args.parked else r.state == "idle":
            print(ctx.m("waited_parked" if args.parked else "waited_idle", id=r.id))
            return
        time.sleep(3)
    sys.exit(ctx.m("timeout", id=args.id, secs=args.timeout))


def cmd_close(ctx, args):
    r = ctx.one(args.id)
    if not args.force:
        if r.private:
            sys.exit(ctx.m("private_close", label=r.label))
        if r.state != "idle":
            sys.exit(ctx.m("not_idle_close", id=r.id, state=ctx.state_label(r.state)))
        if not r.parked:
            sys.exit(ctx.m("not_parked", id=r.id))
    ctx.backend.send(r.terminal, "/exit")
    for _ in range(20):
        time.sleep(0.5)
        if not agents.pid_alive(r.pid):
            break
    ctx.backend.close(r.terminal)
    print(ctx.m("closed", id=r.id, name=ctx.name(r)))


def launch_prompt(ctx, key, thread):
    t = ctx.cfg.topics[key]
    if t.get("prompt"):
        return t["prompt"]
    label = t.get("label", key) + (f"·{thread}" if thread else "")
    d = t.get("dir", ".")
    where = ctx.m("prompt.where", dir=d) if d != "." else ""
    entry = ctx.cfg.resolve(t.get("entry"))
    if entry and entry.exists():
        return ctx.m("prompt.entry", label=label, where=where, entry=t["entry"])
    return ctx.m("prompt.no_entry", label=label, where=where)


def cmd_open(ctx, args):
    topics = ctx.cfg.topics
    if args.topic not in topics:
        sys.exit(ctx.m("unknown_topic", key=args.topic, known=", ".join(topics) or ctx.m("none")))
    t = topics[args.topic]
    if not args.new:
        same = [r for r in ctx.rows() if r.topic == args.topic and (not args.thread or r.thread == args.thread)]
        if same:
            r = max(same, key=lambda r: r.since)
            ctx.backend.focus(r.terminal)
            print(ctx.m("focused", id=r.id, label=r.label))
            return
    label = t.get("label", args.topic) + (f"·{args.thread}" if args.thread else "")
    command = agents.launch_command(ctx.cfg, args.topic, args.thread, launch_prompt(ctx, args.topic, args.thread))
    rgb = COLORS.get(t.get("color", "gray"), COLORS["gray"])
    ctx.backend.open(command, args.topic, args.thread, label, rgb)
    print(ctx.m("opened", label=label, tool=t.get("tool", "claude")))


def cmd_tag(ctx, args):
    if args.topic not in ctx.cfg.topics:
        sys.exit(ctx.m("unknown_topic", key=args.topic, known=", ".join(ctx.cfg.topics)))
    r = ctx.one(args.id)
    ctx.backend.tag(r.terminal, args.topic, args.thread)
    # The state record too: `herd whoami` inside that session reads it.
    for f, d in _state_records(r.terminal):
        d.update(topic=args.topic, thread=args.thread)
        f.write_text(json.dumps(d, ensure_ascii=False))
    print(ctx.m("tagged", id=r.id, label=ctx.cfg.topics[args.topic].get("label", args.topic)))


# ---------- registry ----------


def cmd_topics(ctx, args):
    counts = {}
    try:
        for r in board.collect(ctx.cfg, ctx.backend):
            counts[r.topic] = counts.get(r.topic, 0) + 1
    except Exception:
        pass  # no terminal backend: just skip the "N open" column
    if args.json:
        print(json.dumps({k: {**t, "open": counts.get(k, 0)} for k, t in ctx.cfg.topics.items()}, ensure_ascii=False, indent=1))
        return
    for key, t in ctx.cfg.topics.items():
        n = counts.get(key, 0)
        live = f"  {ctx.m('live', n=n)}" if n else ""
        lock = " 🔒" if t.get("private") else ""
        print(f"{key:<12} {t.get('label', key)}{lock}  {t.get('scope', '')}/{t.get('kind', '')}  [{t.get('tool', 'claude')}]{live}")


def cmd_add(ctx, args):
    cfg = ctx.cfg
    if not cfg.path.exists():
        sys.exit(ctx.m("no_config", path=cfg.path))
    if args.key in cfg.topics:
        sys.exit(ctx.m("topic_exists", key=args.key, path=cfg.path))
    d = cfg.resolve(args.dir)
    if not d.is_dir():
        sys.exit(ctx.m("bad_dir", dir=d))
    rel = str(d.relative_to(cfg.root)) if d.is_relative_to(cfg.root) else str(d)
    block = config.topic_block(
        args.key, args.label, rel, args.scope, args.kind, args.tool, args.color, args.entry, args.private
    )
    with open(cfg.path, "a") as f:
        f.write("\n" + block)
    config.load(cfg.path)  # fail loudly if the file no longer parses
    print(ctx.m("added", label=args.label, key=args.key))


def cmd_init(ctx, args):
    path = ctx.cfg.path
    if path.exists():
        print(ctx.m("init_exists", path=path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# session-herd topic registry. Docs: https://github.com/nightfade/session-herd
[defaults]
root = {config._q(args.root)}        # every session starts here; topic paths are relative to it
language = {config._q(args.language)}
claude = "claude"     # launch command; add flags here, e.g. "claude --model opus"
codex = "codex"

# [manager]
# inbox = "how to capture a stray thought, e.g. append to ~/notes/inbox.md"
# journal = "where the end-of-day summary goes, e.g. ~/notes/daily/{{date}}.md"

[topics.herd]
label = "Herd"
scope = "personal"
kind = "exec"
dir = "."
tool = "claude"
color = "gray"
prompt = "/herd"
"""
    )
    print(ctx.m("init_done", path=path))


def cmd_config(ctx, args):
    cfg = ctx.cfg
    print(json.dumps({"path": str(cfg.path), "defaults": cfg.defaults, "manager": cfg.manager, "topics": cfg.topics}, ensure_ascii=False, indent=1))


# ---------- inside a session ----------


def _state_records(terminal):
    out = []
    for f in STATE_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if d.get("terminal") == terminal:
            out.append((f, d))
    return out


def _own_terminal(ctx):
    me = ctx.backend.current_id()
    if not me:
        sys.exit(ctx.m("not_in_terminal"))
    return me


def cmd_whoami(ctx, args):
    cfg = ctx.cfg
    me = _own_terminal(ctx)
    rec = max((d for _, d in _state_records(me)), key=lambda d: d.get("updated", 0), default={})
    key = os.environ.get("HERD_TOPIC") or rec.get("topic") or cfg.topic_for_cwd(os.getcwd())
    t = cfg.topics.get(key, {})
    handoff = cfg.handoff_file(key) if t else None
    print(
        json.dumps(
            dict(
                topic=key,
                label=t.get("label", ""),
                thread=os.environ.get("HERD_THREAD") or rec.get("thread", ""),
                scope=t.get("scope", ""),
                private=bool(t.get("private")),
                language=ctx.lang,
                entry=str(cfg.resolve(t.get("entry"))) if t.get("entry") else "",
                handoff=str(handoff) if handoff else "",
                handoff_exists=bool(handoff and handoff.exists()),
                handoff_heading=cfg.defaults.get("handoff_heading") or HANDOFF_HEADINGS.get(ctx.lang, "## Handoff"),
                terminal=me,
                now=time.strftime("%Y-%m-%d %H:%M"),
            ),
            ensure_ascii=False,
            indent=1,
        )
    )


def cmd_mark_parked(ctx, args):
    records = _state_records(_own_terminal(ctx))
    if not records:
        sys.exit(ctx.m("no_state"))
    now = time.time()
    for f, d in records:
        d["parked_at"] = now
        f.write_text(json.dumps(d, ensure_ascii=False))
    print(ctx.m("marked_parked"))


# ---------- parser ----------


def build_parser():
    p = argparse.ArgumentParser(prog="herd", description="Herd your Claude Code and Codex sessions by topic.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="every running agent session, the ones waiting on you first")
    s.add_argument("--json", action="store_true")
    s.add_argument("--full", action="store_true", help="include transcript paths in --json")

    s = sub.add_parser("tail", help="last turns of a session's conversation")
    s.add_argument("id")
    s.add_argument("-n", type=int, default=6)
    s.add_argument("--width", type=int, default=600)
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("focus", help="bring a session's tab to the front")
    s.add_argument("id")

    s = sub.add_parser("send", help="type a line into a session and press Enter (idle sessions only)")
    s.add_argument("id")
    s.add_argument("text")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("wait", help="block until a session is idle (or has handed off)")
    s.add_argument("id")
    s.add_argument("--parked", action="store_true")
    s.add_argument("--timeout", type=int, default=600)

    s = sub.add_parser("close", help="exit the agent and close its tab (requires a handoff)")
    s.add_argument("id")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("open", help="open a topic: focus it if already open, else start it in a new tab")
    s.add_argument("topic")
    s.add_argument("thread", nargs="?", default="", help="a second line of work under the same topic")
    s.add_argument("--new", action="store_true", help="open another one even if the topic is open")

    s = sub.add_parser("tag", help="assign a topic to a session that was not opened with herd")
    s.add_argument("id")
    s.add_argument("topic")
    s.add_argument("thread", nargs="?", default="")

    s = sub.add_parser("topics", help="list registered topics")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("add", help="register a topic")
    s.add_argument("key")
    s.add_argument("--label", required=True)
    s.add_argument("--dir", required=True, help="relative to root, or absolute")
    s.add_argument("--scope", default="personal", help="free-form, e.g. personal / work")
    s.add_argument("--kind", choices=["think", "exec"], default="think")
    s.add_argument("--tool", choices=["claude", "codex"], default="claude")
    s.add_argument("--color", choices=list(COLORS), default="gray")
    s.add_argument("--entry", help="document a new session reads first; /park creates it if missing")
    s.add_argument("--private", action="store_true")

    s = sub.add_parser("init", help="create the config file")
    s.add_argument("--root", default="~")
    s.add_argument("--language", choices=["en", "zh"], default="en")

    sub.add_parser("config", help="print the loaded config as JSON")
    sub.add_parser("install", help="add the state hook and skills to Claude Code / Codex")
    sub.add_parser("uninstall", help="remove them again")
    sub.add_parser("whoami", help="(inside a session) my topic and where my handoff goes")
    sub.add_parser("mark-parked", help="(inside a session) record that the handoff is written")
    return p


COMMANDS = {
    "status": cmd_status,
    "tail": cmd_tail,
    "focus": cmd_focus,
    "send": cmd_send,
    "wait": cmd_wait,
    "close": cmd_close,
    "open": cmd_open,
    "tag": cmd_tag,
    "topics": cmd_topics,
    "add": cmd_add,
    "init": cmd_init,
    "config": cmd_config,
    "whoami": cmd_whoami,
    "mark-parked": cmd_mark_parked,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "install":
        return install.install()
    if args.cmd == "uninstall":
        return install.uninstall()
    COMMANDS[args.cmd](Ctx(), args)


if __name__ == "__main__":
    main()
