"""The board: one row per terminal session that runs an agent."""

import time
from dataclasses import asdict, dataclass

from session_herd import agents

STATE_ORDER = {"waiting": 0, "idle": 1, "unknown": 2, "working": 3}


@dataclass
class Row:
    id: str  # short id shown to the user
    terminal: str  # backend-native id
    topic: str
    label: str
    thread: str
    scope: str
    kind: str
    private: bool
    tool: str
    pid: int
    state: str
    since: float
    title: str
    cwd: str
    session_id: str
    peer_name: str
    transcript: str
    parked: bool

    def as_dict(self):
        return asdict(self)


def collect(cfg, backend):
    term = backend.list()
    creg = agents.claude_registry()
    by_tty = agents.agents_by_tty(creg)
    states = agents.hook_states()
    rows = []
    for ts in term:
        if ts.tty not in by_tty:
            continue
        tool, pid = by_tty[ts.tty]
        st = states.get(ts.id, {})
        cr = creg.get(pid, {}) if tool == "claude" else {}
        sid = cr.get("sessionId") or st.get("session_id", "")
        # After /clear the session id changes; a record for the old id is stale.
        if st and sid and st.get("session_id") != sid:
            st = {}
        cwd = cr.get("cwd") or st.get("cwd", "")
        topic = ts.topic or st.get("topic") or cfg.topic_for_cwd(cwd)
        if st.get("state"):
            state, since = st["state"], st.get("since", 0)
        elif cr.get("status"):
            state = "working" if cr["status"] == "busy" else "idle"
            since = cr.get("statusUpdatedAt", 0) / 1000
        else:
            state, since = "unknown", 0
        t = cfg.topics.get(topic, {})
        rows.append(
            Row(
                id=ts.id[:6].lower(),
                terminal=ts.id,
                topic=topic,
                label=t.get("label", ""),
                thread=ts.thread or st.get("thread", ""),
                scope=t.get("scope", ""),
                kind=t.get("kind", ""),
                private=bool(t.get("private")),
                tool=tool,
                pid=pid,
                state=state,
                since=since,
                title=ts.title,
                cwd=cwd,
                session_id=sid,
                peer_name=cr.get("name", ""),
                transcript=st.get("transcript") or agents.find_transcript(tool, sid),
                parked=bool(st.get("parked_at")) and st["parked_at"] >= st.get("last_prompt", 0),
            )
        )
    agents.prune_states({ts.id for ts in term})
    rows.sort(key=lambda r: (STATE_ORDER[r.state], r.since))
    return rows


def resolve(rows, ident):
    """Rows matching a short id, a full terminal id prefix, a topic key or a Claude peer name."""
    ident = ident.lower()
    hits = [r for r in rows if r.id == ident or r.terminal.lower().startswith(ident)]
    return hits or [r for r in rows if r.topic == ident or r.peer_name == ident]


def ago(ts, lang):
    if not ts:
        return "?"
    m = int((time.time() - ts) / 60)
    zh = lang == "zh"
    if m < 60:
        return f"{m}分" if zh else f"{m}m"
    if m < 60 * 24:
        return f"{m // 60}时{m % 60:02d}分" if zh else f"{m // 60}h{m % 60:02d}m"
    return f"{m // 1440}天" if zh else f"{m // 1440}d"
