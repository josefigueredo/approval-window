---
name: approval-demo
description: Use when the user wants to try the approval window (awin) end to end. It runs fake note actions, one per reversibility level, and each one opens the window before anything is written.
---

# approval-demo

Test skill for the `awin` approval window. Notes live in `~/.local/state/approval-demo/notes.json` and are fake.

Run it as `python3 ~/.agents/skills/approval-demo/demo.py <action>` (the skill is installed as a symlink there).

Actions: `delete-note` (irreversible), `share-note` (partial), `rename-notes` (reversible by hand), `archive-notes` and `unarchive-notes` (reversible with a command), and `reset` (irreversible: replaces all notes with the 3 samples; use it when notes ran out).

The window has two buttons, named as they appear on screen: «Apruebo» (approve) and «Cancelar». Use those names
when you talk to the person. Nothing happens until they click «Apruebo».

`archive-notes` acts only on notes not yet archived and `unarchive-notes` only on archived ones; an action with no
matching notes prints `nothing to do: ...` and opens no window.

Exit codes: `0` done (or nothing to do), `2` bad usage, `10` cancelled (the person clicked «Cancelar», closed the window
or let it time out), `69` cannot ask (not macOS, or awin missing: run `install.sh` from the approval-window repo),
`70` a bug (invalid request or an unexpected awin exit code).

## Rules

- Before running an action, tell the user a window will appear, what it will ask them to approve, and that they
  approve with «Apruebo» or refuse with «Cancelar».
- Run exactly one action per request.
- Report the result line the command prints (`done: ...` or `not done: ...`).
- After a cancel, never retry unless the user asks.
- Never try to skip or answer the window; only the person clicks it.
- `python3 ~/.agents/skills/approval-demo/demo.py list` shows the notes (no window).
