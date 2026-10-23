# Choosing a reversibility level

The level is a **fact about the action**, not an opinion about how scary it feels. `awin` picks the color from it;
nobody picks a color by hand.

## The questions, in order

| # | Question | If the answer is… | Level |
|---|---|---|---|
| 1 | ¿Se puede deshacer? Can it be undone at all? | No | `irreversible` |
| 2 | ¿Queda rastro aunque se deshaga? Does it leave a trace others see, even after undoing (notifications, mails, visible history)? | Yes | `partial` |
| 3 | ¿Hay un comando que lo deshace? Is there a real undo command in this CLI, with its own test? | Yes | `reversible_planned` (pass `undo`) |
| 3 | | No, it is undone by hand | `reversible_manual` |

Ask question 1 first. An undo command does not make a sent mail un-sent, and creating issues stays `partial` even if a
command can delete them later: the notifications already went out.

## Examples (from the design)

| Level | Meaning | Examples |
|---|---|---|
| `irreversible` | No way back | Deleting with no trash, sending a mail, overwriting a file with no copy |
| `partial` | Can be reverted, but leaves a trace | Creating issues (notifications go out), editing a PR (history stays) |
| `reversible_manual` | Can be undone, by hand | Moving 10 tickets to another status |
| `reversible_planned` | A known command undoes it | An `apply` with its `undo`; `archive-notes` undone by `unarchive-notes` |

## Traps

- **Local is not the same as harmless.** Deleting the person's saved data from a local file with no backup is
  `irreversible`, audience `me`.
- **Additive local writes do not ask at all.** Saving the item the person just typed is not a level; it is no window.
- **`reversible_planned` needs a real command.** It must exist, be tested, and be named in `undo` exactly as the person
  would run it. Without `undo`, awin shows `reversible_manual` and warns on stderr.
- **Do not invent an undo to lower the level.** If you think the action deserves an undo, that is a separate feature
  for the person to decide; declare today's level.
- **Do not inflate.** Marking everything `irreversible` "just in case" teaches people to click through red.

## Audience

`audience` is required and independent from the level. It says who sees the effect:

| Value | Shown as «Lo ve» | Use when |
|---|---|---|
| `me` | Solo vos | Only this person's data or view changes |
| `team` | Tu equipo | Colleagues see it: a shared board, a team space, a repo |
| `external` | Gente de afuera | People outside the organization: a public link, a customer mail |

## Worked requests

```json
{"skill": "jira-sync", "consequence": "Vas a crear 11 issues en Jira PLATE.",
 "reversibility": "partial", "audience": "team", "approve_label": "Apruebo 11",
 "summary": [["Proyecto", "PLATE"], ["Issues", "11"], ["Épica", "PLATE-120 Pagos"]]}
```

```json
{"skill": "jira-sync", "consequence": "Vas a mover 10 tickets de En curso a Hecho en PLATE.",
 "reversibility": "reversible_manual", "audience": "team", "approve_label": "Apruebo 10"}
```

```json
{"skill": "approval-demo", "consequence": "Vas a archivar 3 notas; dejan de verse en la lista.",
 "reversibility": "reversible_planned", "audience": "me", "undo": "demo.py unarchive-notes",
 "summary": [["Notas", "3"]]}
```
