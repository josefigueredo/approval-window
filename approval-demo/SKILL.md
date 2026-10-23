---
name: approval-demo
description: Use when the user wants to try the approval window (awin) end to end: it runs fake note actions, one per reversibility level, and each one opens the window before anything is written.
---

# approval-demo

Test skill for the `awin` approval window. Notes live in `~/.local/state/approval-demo/notes.json` and are fake.

Run it as `python3 ~/.agents/skills/approval-demo/demo.py <action>` (the skill is installed as a symlink there).

Actions: `delete-note` (irreversible), `share-note` (partial), `rename-notes` (reversible by hand), `archive-notes` and `unarchive-notes` (reversible with a command), and `reset` (irreversible: replaces all notes with the 3 samples; use it when notes ran out).

## Rules

- Before running an action, tell the user a window will appear and what it will ask them to approve.
- Run exactly one action per request.
- Report the result line the command prints (`done: ...` or `not done: ...`).
- After a cancel, never retry unless the user asks.
- Never try to skip or answer the window; only the person clicks it.
- `python3 ~/.agents/skills/approval-demo/demo.py list` shows the notes (no window).
