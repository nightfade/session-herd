# AGENTS.md

Notes for AI agents (and humans) changing this repo.

## Layout

| Path | Role |
|---|---|
| `src/session_herd/hook.py` | lifecycle hook; stdlib only |
| `src/session_herd/paths.py` | config / state locations |
| `src/session_herd/config.py` | topic registry |
| `src/session_herd/agents.py` | processes by tty, Claude's session registry, transcripts, launch command |
| `src/session_herd/board.py` | joins backend sessions, agent processes and hook records into rows |
| `src/session_herd/backends/` | terminal backends; `iterm.py` today |
| `src/session_herd/cli.py` | the `herd` CLI |
| `src/session_herd/install.py` | hook merging and skill links |
| `src/session_herd/i18n.py` | user-facing strings, en / zh |
| `src/session_herd/skills/{park,herd}/SKILL.md` | the two skills, linked into `~/.claude/skills` and `~/.codex/skills` |

Run the tests with `uv run --extra dev pytest`.

## Invariants

- **The hook must never fail visibly.**
  - Always exit 0. Claude Code treats exit code 2 as "block this prompt", so a crash swallows the user's input. The installed command ends with `2>/dev/null || true`, and `main()` catches everything.
  - Print nothing. `SessionStart` and `UserPromptSubmit` stdout goes into the model's context.
  - Keep it standard library only, and fast: it runs on every tool call.
- **Never call `Path.resolve()` or `realpath` on user paths.** Some sandboxed launchers deny realpath on `$HOME`. Use `os.path.normpath`.
- **Launch every session from `root`.** Project instructions, per-directory memory and sandbox scope all follow the launch directory.
- **`send` only types into idle sessions.** At a permission prompt, the Enter would answer the prompt.
- **Private topics are off-limits to the manager.** The CLI enforces this for `tail`, `send` and `close`.

## How state is derived

- **Tab → agent:** match each terminal session's tty to the agent process on that tty (`ps`).
- **Which Claude process:** wrappers share the tty with the real agent, so prefer the pid that has a record in `~/.claude/sessions/<pid>.json`. That record also gives the session id, the peer name and busy/idle.
- **Topic**, first match wins:
  1. the backend's tag (iTerm2 user variable `user.herd_topic`);
  2. the hook record's `HERD_TOPIC`;
  3. the topic whose `dir` contains the session's cwd.
- **State:** the hook record wins. Without one, fall back to Claude's busy/idle.
- **Waiting:** for Claude, only the `permission_prompt` Notification. Claude's `PermissionRequest` also fires for requests that auto mode approves, so it is not installed. For Codex, `PermissionRequest`.
- **Parked:** `parked_at >= last_prompt`.
- **Stale records:** a record whose session id differs from the live one is stale (after `/clear`). `herd status` deletes records whose terminal session is gone.

## Adding a backend

Implement `session_herd.backends.Backend`: `current_id`, `list`, `focus`, `send`, `close`, `open`, `tag`.

- `list` returns `TermSession(id, tty, title, topic, thread)`.
- The hook records the terminal id from the environment: `ITERM_SESSION_ID` (UUID part) or `TMUX_PANE`. Make `current_id` agree with it.
