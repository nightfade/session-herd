"""Terminal backends. A backend lists terminal sessions and can focus, type into, open and close them.

Only iTerm2 is implemented today; tmux will implement the same interface.
"""

import os
from dataclasses import dataclass


@dataclass
class TermSession:
    id: str  # backend-native unique id (iTerm2 session UUID)
    tty: str
    title: str
    topic: str  # tag set by `herd open` / `herd tag`
    thread: str


class Backend:
    name = ""

    def current_id(self):
        """Id of the terminal session this process runs in, or "" if unknown."""
        raise NotImplementedError

    def list(self):
        raise NotImplementedError

    def focus(self, sid):
        raise NotImplementedError

    def send(self, sid, text):
        """Type text into the session and press Enter."""
        raise NotImplementedError

    def close(self, sid):
        raise NotImplementedError

    def open(self, command, topic, thread, label, rgb):
        """Open a new tab, tag it with topic/thread, run command in it. Returns the new session id."""
        raise NotImplementedError

    def tag(self, sid, topic, thread, label, rgb):
        """Tag the session with topic/thread and give it the topic's tab color and badge."""
        raise NotImplementedError


def get_backend(name=None):
    # iTerm2 is the only backend so far; tmux will be picked when $TMUX is set.
    name = name or os.environ.get("HERD_BACKEND") or "iterm2"
    if name == "iterm2":
        from session_herd.backends.iterm import ITerm2Backend

        return ITerm2Backend()
    raise ValueError(f"unknown backend: {name}")
