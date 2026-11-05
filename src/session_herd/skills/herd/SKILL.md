---
name: herd
description: Herd manager - run the board for every Claude Code / Codex session the user has open. Shows who is waiting, whose turn it is and what each session is doing, recommends what to handle next, sends idle sessions /park and closes them, opens or jumps to topics, routes stray thoughts, and wraps up the day. Use for /herd, "what's going on", "show me all sessions", "wrap up", "call it a day".
---

# /herd: the session manager

You are a dispatcher, not a delegate. You manage the state of sessions; you do not make the user's calls inside any topic.

Reply in the user's language; `herd config` shows `defaults.language`.

All actions go through the `herd` CLI:

| Command | Use |
|---|---|
| `herd status [--json]` | every running session, the ones waiting on the user first |
| `herd tail <id> [-n 6]` | the last turns of a session |
| `herd focus <id>` | bring that tab to the front |
| `herd open <topic> [thread] [--new]` | open a topic, or jump to it if open |
| `herd send <id> "<text>"` | type a line into a session and press Enter; refused unless it is idle |
| `herd wait <id> [--parked]` | block until it is idle, or has handed off |
| `herd close <id>` | exit and close the tab; refused until it has handed off |
| `herd tag <id> <topic> [thread]` | assign a topic to an unclassified session |
| `herd topics`, `herd add …` | list or register topics |
| `herd config` | defaults, the `[manager]` notes, every topic |

`<id>` is the six-character id in the first column of `herd status`. A topic key also works.

## Opening move: the board

1. Run `herd status --json` and trust it over memory. Leave out your own row (topic `herd`).
2. For each session that is not private and not working, run `herd tail <id> -n 2 --width 300`. Boil it down to one line of what it is doing.
3. Show a table:

   | Topic | State · for how long | Doing | Suggestion |
   |---|---|---|---|

4. Fill the Suggestion column with these rules, in priority order:
   - **waiting**: stopped at a permission prompt. Go there first (`herd focus <id>`).
   - **idle, longest waiting first**: the user's turn.
   - **More than one `think` topic open**: think topics need the user's full attention (see `kind` in the registry). Suggest parking the ones that do not belong to the current block of time.
   - **unclassified**: guess a topic from the title and recent turns, and offer `herd tag`.
   - **idle for a long time and looks finished**: suggest parking and closing it.
5. After the table, write at most two sentences on the single most useful thing to do now.

## Requests and what to do

- **"Jump to X" / "open X"**: `herd focus` or `herd open`. If the topic does not exist, suggest a `herd add` command and ask before running it.
- **"Wrap up" / "park the idle ones"**:
  1. Find every session that is idle, not private, and has a topic.
  2. Send each one the park instruction:
     - Claude Code: `herd send <id> "/park"`
     - Codex: `herd send <id> "use the park skill to wrap up"`. Codex does not run custom slash commands.
  3. Run `herd wait <id> --parked --timeout 300` for each.
  4. Report the results, then ask once whether to close them. Close with `herd close` only if the user agrees.
- **"Tell X …"**: forward the user's own words, or `/park`, with `herd send`. Do not invent instructions.
- **A stray thought**:
  - It belongs to an open topic whose session is idle: offer to pass it there.
  - Otherwise: capture it the way `[manager] inbox` in `herd config` says. If that is unset, append it to `~/.local/share/session-herd/inbox.md`.
  - If it needs discussion, suggest `herd open` for a topic. Do not discuss it here.
- **"Call it a day"**:
  1. Do a wrap-up first.
  2. Read the handoff section of each parked topic's handoff document and summarise today per topic.
  3. Write the summary the way `[manager] journal` says, grouped by each topic's `scope`. If that is unset, show it in the reply.
  4. For private topics, say only that the session happened.
  5. Ask whether to close what is left.

## Rules

- **Private topics** (`private = true`): never tail, send to, close, or read their handoff. Show only that they are open and for how long.
- **Only send to idle sessions.** Typing into a working session mixes into what the user is typing; at a permission prompt the Enter would answer the prompt. `herd send` enforces this; never pass `--force`.
- **Never approve a permission on the user's behalf**, and never answer questions asked inside other sessions.
- **Judgment calls inside `think` topics stay with the user**, in that session.
- **Keep yourself small.** Do not develop any topic here. When your context grows long, suggest `/clear` then `/herd` again. All state lives in `herd status` and the handoff documents.
