---
name: approval-window
description: Use when building or changing a skill's CLI that performs an action with effects outside the process (writes to a shared system, deletes, sends, publishes or overwrites data) and a person must approve it first; teaches when to ask, which reversibility level to declare, how to write the consequence, and how to wire and test the `awin` approval window. Not for read-only commands.
---

# approval-window

`awin` is a global command (on the PATH) that shows a native macOS window with what is about to happen and waits for
one click. A skill's CLI calls it **right before** a consequential action and acts **only** if it exits `0`.

The window does not stop rubber-stamping by itself: a person approved one without reading after 12 identical windows.
Every window you add spends the person's attention. **Ask rarely, ask only when it matters, and say exactly what
will happen.** An extra window is a bug, not caution.

Full contract (keys, limits, exit codes): [references/protocol.md](references/protocol.md).
Level decision with examples: [references/choosing-a-level.md](references/choosing-a-level.md).
Wiring and testing details: [references/wiring.md](references/wiring.md).
Request check to copy into your tests: [references/check_request.py](references/check_request.py).

## 1. Which actions ask

List every command of the CLI and mark the ones that **destroy, overwrite, send, publish, or write to something other
people or systems share**. Only those ask.

| Asks | Never asks |
|---|---|
| Destroying or overwriting **the person's data** with no trash, even in a local file (their notes, drafts, config) | Reading, listing, searching, `--dry-run`, `plan` |
| Writing to Jira, Confluence, GitHub, a database, a shared drive | Adding something the person just asked for (append a note, save a draft) |
| Sending a mail or message, publishing a page, pushing | Disposable CLI state: caches, temp files, lock files, logs, anything the CLI can rebuild |
| Bulk **destructive or shared** changes (delete 40 files, move 10 tickets) | An action with nothing to do (0 items): print it and exit without a window |

- **One window per user intent, never per item.** "Create 11 issues" is one window with `"approve_label": "Apruebo 11"`
  and the list in `detail`; never 11 windows. Never call `awin` in a loop.
- Ask **after** you computed exactly what will happen (the plan), **before** the first write.
- If the command already has a plan/apply split, the window goes in `apply`, once.

## 2. Pick the level (a fact, not a mood)

Answer in this order; the first match decides:

1. **Can it be undone at all?** No (delete with no trash, a sent mail, an overwrite with no copy) → `irreversible`.
2. **Does it create something others already received or saw, which undoing does not remove?** Notifications, mails,
   new items, edited content others read (created issues, an edited PR) → `partial`.
3. **Is there a real, tested command that undoes it?** Yes → `reversible_planned`, and pass it in `undo`.
   No → `reversible_manual`.

Moving 10 tickets to another status is `reversible_manual`: moving them back restores the state and nothing new was
sent. Creating 11 issues is `partial`: deleting them does not un-send the notifications.

Rules:
- `reversible_planned` **only** with an undo command that exists in this CLI and has its own test. Without `undo`, awin
  downgrades it to `reversible_manual` anyway.
- Do not build a backup or undo feature just to lower the level. Declare the level the action has today.
- Do not push everything to `irreversible` "just in case", nor to the lowest level "so it doesn't bother". Both turn
  the window into noise.
- `audience` is required and is also a fact: `me` (only this person sees the effect), `team` (colleagues see it),
  `external` (people outside the org).

## 3. Write the consequence

`consequence` is the heading the person reads, in Spanish (voseo), ≤ 140 characters:

> **Vas a \<verbo\> \<cantidad\> \<qué\> en \<dónde\>.**

- Concrete numbers and names: «Vas a crear 11 issues en Jira PLATE.», «Vas a borrar tus 14 borradores de drafts-cli para siempre.»
- Count-aware: «tu borrador» for one, «tus 3 borradores» for many; never «tus 1 borradores».
- No jargon, flags, ids without a name, or command lines. Not «Ejecutar sync --apply».
- `summary` (≤ 6 rows) answers what a person would ask before clicking: how many, where, which ones, what remains.
- `detail` holds the full item list (folded). `risk_note` only when the default text per level says too little.
- `approve_label` with the count for batches: «Apruebo 11».
- Cut text that comes from data before sending: summary values to 100, detail lines to 300, names inside the
  consequence so it stays ≤ 140. Helpers in [references/wiring.md](references/wiring.md).

```json
{"skill": "drafts-cli", "consequence": "Vas a borrar tus 14 borradores de drafts-cli para siempre.",
 "reversibility": "irreversible", "audience": "me", "approve_label": "Apruebo 14",
 "summary": [["Borradores", "14"], ["Carpeta", "~/Library/Application Support/drafts-cli"]],
 "detail": ["Propuesta Q4", "Respuesta a Ana", "..."]}
```

## 4. Wire it

Build the JSON, find `awin` on the PATH, pass the JSON on stdin, map its exit code to **your CLI's own codes**. Make
the call injectable. This is the whole pattern:

```python
import json, shutil, subprocess, sys

EXIT_USAGE = 2          # the CLI's own codes, documented in its usage/README
EXIT_CANCELLED = 10     # awin 1
EXIT_UNAVAILABLE = 69   # awin 3 or awin missing (sysexits EX_UNAVAILABLE)
EXIT_SOFTWARE = 70      # awin 2 or anything unexpected (sysexits EX_SOFTWARE)


def default_run_awin(request):
    """Run the real awin with the request on stdin; return its exit code (3 when awin is missing)."""
    exe = shutil.which("awin")
    if not exe:
        return 3                            # the caller prints the one message
    return subprocess.run([exe], input=json.dumps(request), universal_newlines=True).returncode


def ask(run_awin, request):
    """Return None when approved, else the CLI exit code after printing one line."""
    code = run_awin(request)
    if code == 0:
        return None
    if code == 1:
        print("not done: cancelled")
        return EXIT_CANCELLED
    if code == 3:
        print("not done: cannot ask for approval; needs macOS and awin (install approval-window)", file=sys.stderr)
        return EXIT_UNAVAILABLE
    if code == 2:
        print("not done: invalid approval request (bug in drafts-cli)", file=sys.stderr)
    else:
        print("not done: unexpected awin exit code %s" % code, file=sys.stderr)
    return EXIT_SOFTWARE


def cmd_purge(run_awin):
    drafts = load_drafts()
    if not drafts:
        print("nothing to purge")           # no window for a no-op
        return 0
    refused = ask(run_awin, purge_request(drafts))   # request built as in step 3
    if refused is not None:
        return refused                      # nothing written
    delete_all(drafts)                      # write ONLY here
    print("deleted %d drafts" % len(drafts))
    return 0


def main(argv, run_awin=None):
    run_awin = run_awin or default_run_awin
    ...
```

- Exit `0`: act. `1`: report "cancelled", write nothing, do not retry. `2`: a bug in your request; write nothing and
  fix the code. `3` or `awin` missing: refuse with **one** message saying what to install; never fall back to writing.
- Never pass awin's codes straight through: they collide with your own (awin 2 is not your usage error). Pick codes,
  document them, test them ([references/wiring.md](references/wiring.md)).
- **Never** add `--yes`, `--force`, an environment variable, a config flag, a pre-approval file or any other path that
  skips the window. Tests inject the call instead (step 5).
- Never answer, click or automate the window, and never retry after a cancel unless the person asks.
- When an agent runs the command, it tells the person first that a window will appear and what it asks.

A fuller worked example lives in the approval-window repo, at
`$(dirname "$(readlink ~/.local/bin/awin)")/approval-demo/demo.py`, with its tests in `tests/test_demo.py` there.
Reading it is optional: the pattern above is the same.

## 5. Test it

Never call the real `awin` from tests (a real window would pop up). Adding the seam changes `main` to
`main(argv, run_awin=None)`, so **update every existing test** to inject a fake. Default the fake to cancelled, so a
forgotten case writes nothing:

```python
class Fake:
    def __init__(self, code=1):             # default: cancelled
        self.code, self.requests = code, []

    def __call__(self, request):
        self.requests.append(request)
        return self.code
```

Cover, for each action that asks:
- `Fake(0)` writes; `Fake(1)`, `Fake(2)` and `Fake(3)` leave the data untouched (compare before and after) and exit
  with the CLI's mapped codes;
- exactly one request per command, with the expected `reversibility`, `audience` and count in `consequence`
  (one item and several);
- commands that must not ask (read-only, additive, no-op) leave `fake.requests` empty;
- `default_run_awin` with `awin` missing (`mock.patch("shutil.which", return_value=None)`) returns 3, and the command
  prints exactly one message;
- every recorded request passes `check_request` from [references/check_request.py](references/check_request.py), copied
  into your tests (stdlib only). When the approval-window repo is importable, also assert
  `awin.request.parse(request).warnings == ()`; that is extra, never a reason to skip.

## Checklist

- [ ] Only destructive, outward or shared writes ask; read-only, additive, disposable-state and no-op commands do not.
- [ ] One window per intent, before the first write, never in a loop.
- [ ] Level chosen by the three questions; `reversible_planned` only with a real, tested `undo`.
- [ ] `audience` set; `consequence` is «Vas a …» with count-aware numbers and names, ≤ 140 chars; data cut to limits.
- [ ] Writes only on exit 0; awin codes mapped to documented CLI codes; one message when awin is missing.
- [ ] No bypass of any kind.
- [ ] Existing tests updated to inject a fake (default cancelled); new tests prove no write on 1, 2 and 3 and run
      `check_request` on every request.
