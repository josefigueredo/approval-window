# awin protocol

`awin` reads one JSON request (stdin, or `--spec FILE`), shows the window, and answers with one word and an exit code.
The caller sends **data, never HTML**: every string is escaped and the web view runs with JavaScript disabled.

Human-facing version (Spanish): `docs/referencia.md` in the approval-window repo.

## Request

A JSON object. Unknown keys are rejected with exit 2 (so `"approved": true` or `"yes": true` never approve anything).

| Key | Type | Required | Limit / values |
|---|---|---|---|
| `skill` | str | yes | 1–40 chars; shown in the title bar |
| `consequence` | str | yes | 1–140 chars; the heading |
| `reversibility` | str | yes | `irreversible`, `partial`, `reversible_manual`, `reversible_planned` |
| `audience` | str | yes | `me`, `team`, `external` |
| `risk_note` | str | no | ≤ 140; defaults per level below |
| `undo` | str | required for `reversible_planned` | ≤ 200; shown as a row |
| `summary` | list of `[label, value]` | no | ≤ 6 rows; label 1–30, value ≤ 100 |
| `detail` | list of str | no | lines ≤ 300 chars; past 200 lines, truncated with «… y N más» |
| `approve_label` | str | no | 1–24 chars; default `Apruebo` |
| `style` | str | no | `alert` (default), `edge`, `tag` |

Every string (summary labels and values and detail lines too) is rejected with exit 2 when it holds a control
character (U+0000–U+001F, so newlines and tabs too, or U+007F), a lone surrogate, or a bidi override or isolate
(U+202A–U+202E, U+2066–U+2069). `skill`, `consequence` and `approve_label` must not be only whitespace.

Default `risk_note`:

| Level | Text | Color |
|---|---|---|
| `irreversible` | No se puede deshacer. | `#ff3b30` |
| `partial` | Se puede revertir, pero deja rastro. | `#ff9f0a` |
| `reversible_manual` | Se puede deshacer, pero a mano. | `#ffcc00` |
| `reversible_planned` | Se puede deshacer con un comando. | `#0a84ff` |

Row «Lo ve» from `audience`: `me` «Solo vos», `team` «Tu equipo», `external` «Gente de afuera».

`reversible_planned` without `undo` is not an error: it is shown as `reversible_manual` and awin prints
`awin: reversible_planned without undo; shown as reversible_manual` to stderr.

## Response

One word on stdout (`approved` or `cancelled`), only with exit 0 or 1.

| Exit | Meaning | What the caller does |
|---|---|---|
| `0` | approved: the person clicked Approve | Act |
| `1` | cancelled, closed, timed out, or something failed | Write nothing; report "cancelled"; do not retry |
| `2` | invalid input; the window never opened; reason on stderr | Write nothing; it is a bug in the caller |
| `3` | no window available (not macOS, no `/usr/bin/osascript`, osascript failed) | Refuse with a clear message |

A missing `awin` on the PATH is handled by the caller as exit 3.

Exit 0 means approved only together with stdout `approved`. `-h` and `--version` also exit 0 and print no
`approved`; the wiring never passes options. Options are never abbreviated: `--v` or `--t 30` exit 2.

## Options

| Option | Effect |
|---|---|
| `--spec FILE` | Read the request from a file instead of stdin |
| `--timeout SECONDS` | Wait less; never more than the maximum (100 s, under Cursor's 120 s tool cut) |
| `--version` | Prints `awin 0.1.0` |

## Guarantees

- Nothing approves without a click: no `--yes`, environment variable, pre-approval file or default button. Enter never
  approves; Escape, closing, a failure and the timeout all mean `cancelled`.
- Approve is disabled until the page has loaded. One system beep when the window appears, at every level.
- It does **not** guarantee the person reads. That is why skills ask rarely and write consequences worth reading.

## Minimal valid request

```json
{"skill": "drafts-cli", "consequence": "Vas a borrar tus 14 borradores de drafts-cli para siempre.",
 "reversibility": "irreversible", "audience": "me"}
```
