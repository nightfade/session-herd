"""iTerm2 backend over iTerm2's Python API (a unix socket).

The socket works where AppleScript does not: agents that run inside a macOS
sandbox usually cannot send Apple Events, but can still connect to the socket.
Requires Settings > General > Magic > Enable Python API.
"""

import asyncio
import os

import iterm2
from websockets.exceptions import ConnectionClosed

from session_herd.backends import Backend, TermSession

TOPIC_VAR = "user.herd_topic"
THREAD_VAR = "user.herd_thread"


class ITerm2Backend(Backend):
    name = "iterm2"

    def _run(self, fn):
        out = {}

        async def main(conn):
            # The app object refreshes itself on layout changes (e.g. a new tab); refreshes still
            # pending when we disconnect fail with ConnectionClosed. Those are harmless; drop them.
            loop = asyncio.get_running_loop()

            def on_error(loop, ctx):
                if not isinstance(ctx.get("exception"), ConnectionClosed):
                    loop.default_exception_handler(ctx)

            loop.set_exception_handler(on_error)
            out["v"] = await fn(conn, await iterm2.async_get_app(conn))

        iterm2.run_until_complete(main, retry=False)
        return out.get("v")

    @staticmethod
    def _sessions(app):
        for w in app.terminal_windows:
            for t in w.tabs:
                yield from t.sessions

    def current_id(self):
        return os.environ.get("ITERM_SESSION_ID", "").split(":", 1)[-1]

    def list(self):
        async def fn(conn, app):
            out = []
            for s in self._sessions(app):
                out.append(
                    TermSession(
                        id=s.session_id,
                        tty=await s.async_get_variable("tty") or "",
                        title=await s.async_get_variable("autoName") or "",
                        topic=await s.async_get_variable(TOPIC_VAR) or "",
                        thread=await s.async_get_variable(THREAD_VAR) or "",
                    )
                )
            return out

        return self._run(fn)

    def _with_session(self, sid, action):
        async def fn(conn, app):
            s = app.get_session_by_id(sid)
            if s is None:
                raise LookupError(sid)
            return await action(conn, app, s)

        return self._run(fn)

    def focus(self, sid):
        async def action(conn, app, s):
            await s.async_activate(select_tab=True, order_window_front=True)
            await app.async_activate()

        self._with_session(sid, action)

    def send(self, sid, text):
        async def action(conn, app, s):
            await s.async_send_text(text)
            # A separate Enter, so TUIs see typed text followed by a submit rather than one paste.
            await asyncio.sleep(0.4)
            await s.async_send_text("\r")

        self._with_session(sid, action)

    def close(self, sid):
        async def action(conn, app, s):
            await s.async_close(force=True)

        self._with_session(sid, action)

    @staticmethod
    async def _style(s, topic, thread, label, rgb):
        await s.async_set_variable(TOPIC_VAR, topic)
        await s.async_set_variable(THREAD_VAR, thread)
        change = iterm2.LocalWriteOnlyProfile()
        change.set_tab_color(iterm2.Color(*rgb))
        change.set_use_tab_color(True)
        change.set_badge_text(label)
        await s.async_set_profile_properties(change)

    def tag(self, sid, topic, thread, label, rgb):
        async def action(conn, app, s):
            await self._style(s, topic, thread, label, rgb)

        self._with_session(sid, action)

    def open(self, command, topic, thread, label, rgb):
        async def fn(conn, app):
            window = app.current_terminal_window
            if window is None:
                window = await iterm2.Window.async_create(conn)
                s = window.current_tab.current_session
            else:
                s = (await window.async_create_tab()).current_session
            await self._style(s, topic, thread, label, rgb)
            await s.async_send_text(command + "\r")
            await s.async_activate(select_tab=True, order_window_front=True)
            await asyncio.sleep(0.5)  # let the layout-change refresh finish before disconnecting
            return s.session_id

        return self._run(fn)
