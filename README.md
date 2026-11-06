# session-herd

Herd your Claude Code and Codex sessions.

If you keep a dozen agent sessions open across terminal tabs, the tabs are not the problem. You are: every session eventually queues up for the same person to read, answer, or approve. session-herd keeps that queue small and visible:

- **One tab per topic.** Each topic has a home: a directory, an entry document, and a handoff file. Tabs are disposable.
- **Handoffs instead of open loops.** `/park` writes three lines (where things stand, next step, open questions) before you leave. The next session for that topic picks up in thirty seconds.
- **A board that says who needs you.** Every session shows as *waiting* (stuck at a permission prompt), *your turn*, or *working*, with the ones waiting on you first.
- **An agent that runs the board.** `/herd` turns one Claude session into a dispatcher. It shows the board, tells you what to handle next, parks idle sessions and closes them, and wraps up the day.

It works for any kind of topic, not just code: investing notes, journaling, language practice, photo reviews.

[中文说明](README.zh-CN.md) · [Why it works this way](docs/methodology.md)

## Requirements

- macOS with **iTerm2**, with the Python API enabled: Settings → General → Magic → *Enable Python API*. tmux support is planned.
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pipx).
- Claude Code and/or Codex CLI.

## Install

```bash
uv tool install git+https://github.com/nightfade/session-herd
herd init --root ~/work          # every session will start in this directory
herd install                     # adds the state hook and the /park and /herd skills
```

`herd install` merges hook entries into `~/.claude/settings.json` and `~/.codex/hooks.json`, backs both files up first, and links the skills into `~/.claude/skills` and `~/.codex/skills`. Run it again after upgrading; `herd uninstall` removes everything it added.

Codex runs hooks only with `[features] hooks = true` in `~/.codex/config.toml`, and asks you to approve new hooks on its next start.

## Daily use

| You want to | Run |
|---|---|
| list topics | `herd topics` |
| open a topic | `herd open invest`. Jumps to it if open; otherwise opens a colored, badged tab that reads the entry doc and picks up the last handoff |
| a second line of work in one topic | `herd open api auth-refactor`, or add `--new` |
| see every session | `herd status` |
| register a topic | `herd add garden --label Garden --dir notes/garden --kind think` |
| leave a session | type `/park` in it, then close the tab |
| reopen a closed session | `herd resume <session-id> --topic api`. Picks Claude or Codex from the id and starts in the session's original directory |
| start the manager | `herd open herd`, or type `/herd` in any Claude session |

A short alias helps: `alias t='herd open'`.

### Talking to the manager

| Say | It does |
|---|---|
| what's going on | the board: topic, state and for how long, what each session is doing, a suggestion |
| jump to X / open X | focuses or opens the topic |
| wrap up | sends `/park` to idle sessions, waits for the handoffs, offers to close them |
| tell X … | forwards your words to an idle session |
| call it a day | wrap up, write the day's summary, offer to close the rest |

## The topic registry

`~/.config/session-herd/topics.toml` is the only file you edit. See [examples/topics.toml](examples/topics.toml).

```toml
[defaults]
root = "~/work"        # all sessions start here; paths below are relative to it
language = "en"        # en | zh
claude = "claude"      # launch commands, with your usual flags
codex = "codex"

[scopes.work]          # per-scope launch commands, override [defaults]
claude = "claude --model sonnet"

[manager]
inbox = "append the thought to notes/inbox.md"
journal = "append to notes/daily/<today>.md"

[topics.invest]
label = "Investing"
scope = "personal"     # free-form; the day's summary is grouped by it
kind = "think"         # think: needs your full attention | exec: an agent working on its own
dir = "notes/investing"
entry = "notes/investing/README.md"   # read first by every new session
handoff = "notes/investing/HANDOFF.md" # where /park writes; defaults to entry
tool = "claude"        # claude | codex
color = "green"
private = false        # true: the manager never reads, types into or closes it
# command = "..."      # launch command for this topic only; overrides scopes and defaults
# prompt = "..."       # replaces the default opening prompt
```

Sessions always start in `root`, not in the topic's directory. Project instructions (`CLAUDE.md`, `AGENTS.md`) and per-directory memory are found from the launch directory. Sandboxed launchers also scope file access to it. The topic's `dir` goes into the opening prompt instead.

## How it works

- A hook (`python -m session_herd.hook`) runs on every Claude Code / Codex lifecycle event. It writes the session's state to `~/.cache/session-herd/state/`:
  - a permission dialog on screen → waiting (Claude's `permission_prompt` notification, Codex's `PermissionRequest`);
  - `Stop` → your turn;
  - tool calls and prompts → working.
  It prints nothing and always exits 0, because Claude Code treats exit code 2 as "block this prompt".
- `herd status` joins three things:
  - iTerm2's sessions, via the Python API socket. This works even from sandboxed agents that cannot send Apple Events;
  - the agent process on each tty;
  - Claude Code's own session registry and the hook records.
- `herd open` tags the new tab with the topic (an iTerm2 user variable) and starts the agent with `HERD_TOPIC` set. It sets the tab color and a badge.
- `herd send` types into a tab, but only when that session is idle. Typing into a busy session would mix with your input, and at a permission prompt the Enter would answer it.

## Status

Early. Tested with Claude Code on iTerm2. Codex support is wired in (hooks, transcripts, skills) but less exercised. Planned next: a tmux backend.

## License

MIT
