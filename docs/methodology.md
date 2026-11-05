# Methodology

Why session-herd works the way it does.

## Principles

- **The bottleneck is you, not the number of windows.** Every session ends up waiting for the same person to read, answer, or approve.
- **Switching is cheap; resuming is expensive.** Leave the context in a file, not in your head.
- **Run `exec` topics in parallel. Run `think` topics one at a time.**
- **A topic lives in files, not in a window.** Close tabs freely; reopening takes thirty seconds.
- **A stray thought does not get a new window.** It goes to an inbox until its time comes.

## Why juggling sessions is tiring

- **Queueing.** Waiting time grows with utilisation as ρ/(1−ρ). By that model, at 80% busy each request waits four times as long as at 50%. Agents started together also tend to ask for you together.
- **Resumption cost.** In Parnin and Rugaber's study of about 10,000 programming sessions, only about 10% resumed coding within a minute.
- **Attention residue.** Leaving a task unfinished leaves part of your attention behind on it (Sophie Leroy). Writing down how you will resume reduces the residue.
- **Open loops.** An open window is an unfinished thing, and it keeps occupying you.

## Two kinds of sessions

| Kind | Examples | Rule |
|---|---|---|
| `exec` | coding, generating reports, bookkeeping runs, sorting photos, research | Parallel is fine. Brief it well, let it run, look when it calls you |
| `think` | investment decisions, journaling, critique sessions, language practice, career planning | One per block of time. Every turn needs your thinking, so parallel sessions only make each one shallower |

Size your parallelism by what you can actually review, not by what the tools allow. A workable default:

- one or two sessions that need your thinking or review;
- a few low-stakes background ones.

## Order of service

1. **Unblock first.** A session stuck at a permission prompt wastes time every minute. Finished work loses nothing by waiting.
2. **Then the longest-waiting *your turn*.** Notifications push you toward the most recent one, which is the wrong order.
3. **Review last.**

## Fewer interruptions

- Hand an agent a larger chunk. Say what you want, and settle in advance the decisions it would otherwise ask about.
- Once the direction is set, let it run to completion. It can make small calls itself and report them.

## Rhythm

- Group topics into blocks of time. Do not hop between work and personal topics every ten minutes; cross-domain switches cost the most.
- Give emotionally heavy topics a block of their own. Never leave one running in the background. Close it with a handoff.
- Use one tool per topic (Claude Code or Codex), so you never have to remember where you discussed something.

## Leaving and returning

- **Leaving:** `/park` writes three lines (where things stand, next step, open questions), then close the tab. If three lines cannot capture it, you are not at a point where you can leave.
- **Returning:** `herd open <topic>`. The new session reads the handoff and tells you where things stand. You do not have to remember.

## The manager

- **A dispatcher, not a delegate.** It manages session state. It does not make calls inside topics and never approves permissions.
- **Look at it at two moments only:** when a block of time changes ("what next?") and at the end of the day ("call it a day").
- **Let the terminal's own status markers find you the rest of the time.** Asking the manager before every action is one more switch, not one fewer.

## References

- Gabriel Anhaia, *Five Parallel Coding Agents Won't Make You 5x Faster. You Are the Queue*
- Johannes Jo, *Why Multitasking With AI Coding Agents Breaks Down*
- *Running three coding agents at once is easy. Noticing when they need you isn't*
- Anthropic, *Claude Code power user tips*
- Chris Parnin and Spencer Rugaber, *Resumption strategies for interrupted programming tasks*
- Sophie Leroy, *Why is it so hard to do my work? The challenge of attention residue when switching between work tasks*
