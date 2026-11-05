---
name: park
description: Wrap up the current session before switching away - write a three-line handoff (where things stand, next step, open questions) into this topic's handoff document and mark the session as handed off, so the window can be closed without losing anything. Use when the user says "park", "hand off", "wrap up", "I'm switching away", or when the herd manager sends /park.
---

# /park: write the handoff, then the window can close

Goal: the next session that opens this topic picks up in thirty seconds, and the user stops carrying this topic in their head.

Reply in the user's language. Write the handoff in the language given by `language` from `herd whoami`.

## Steps

1. Run `herd whoami`. It returns:
   - who this session is: `topic`, `label`, `thread`, `private`;
   - where the handoff goes: `handoff`, `handoff_heading`;
   - `language` and the current time `now`.

2. If `topic` is empty, this session was not opened with `herd open` and has not been tagged:
   - If the manager sent the /park, do not stop to ask. Skip writing and reply that the session is unclassified and no handoff was written.
   - Otherwise:
     1. Run `herd topics`, guess the topic from the conversation, and ask the user to confirm.
     2. If no topic fits, suggest a `herd add <key> --label <name> --dir <dir>` command and run it once the user agrees.
     3. Run `herd tag <first 6 chars of terminal> <topic> [thread]`, then `herd whoami` again.

3. Write the handoff into the file at `handoff`:
   - If the file does not exist, create it with a title `# <label>` and only the handoff section.
   - Find the section titled `handoff_heading`. If there is none, add it after the first top-level heading and its intro paragraph.
   - Inside it, give each thread its own subsection: `### <thread, or "main" (zh: 主线)> (<now>)`. Replace only your own subsection; leave other threads alone.
   - Each subsection has exactly three lines:

     | en | zh | content |
     |---|---|---|
     | **Where things stand** | **现在在哪** | what is done and which files hold the output |
     | **Next step** | **下一步** | the first thing to do when picking this up |
     | **Open questions** | **悬着的问题** | decisions waiting on the user; "none" (zh: 无) if there are none |

   - Write conclusions, not the story of how you got there.
   - If a thread is finished and has no next step, delete its subsection instead of writing "done".

4. If the file already has its own structure (front matter, a startup script, its own "current state" section), follow that structure:
   - update its date field and the relevant section;
   - do not add a generic handoff section;
   - do not expand the document beyond what the handoff needs.

5. Run `herd mark-parked`.

6. Reply with one line: the handoff is written to `<path>` and the window can be closed.

## Don't

- Edit anything outside the handoff section.
- Settle open questions on the user's behalf.
- Force it. If three lines cannot capture where things are, the session is not at a point where it can be left. Say so.
