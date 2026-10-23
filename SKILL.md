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

## 1. Which actions ask

List every command of the CLI and mark the ones that **destroy, overwrite, send, publish, or write to something other
people or systems share**. Only those ask.

| Asks | Never asks |
|---|---|
| Deleting or overwriting the person's data with no trash (even a local file) | Reading, listing, searching, `--dry-run`, `plan` |
| Writing to Jira, Confluence, GitHub, a database, a shared drive | Adding something the person just asked for, locally (append a note, create a draft file) |
| Sending a mail or message, publishing a page, pushing | Caches, temp files, scratch work inside the CLI's own state |
| Bulk changes to many items | An action with nothing to do (0 items): print it and exit without a window |

- **One window per user intent, never per item.** "Create 11 issues" is one window with `"approve_label": "Apruebo 11"`
  and the list in `detail`; never 11 windows. Never call `awin` in a loop.
- Ask **after** you computed exactly what will happen (the plan), **before** the first write.
- If the command already has a plan/apply split, the window goes in `apply`, once.

## 2. Pick the level (a fact, not a mood)

Answer in this order; the first "yes"/"no" that matches decides:

1. **Can it be undone at all?** No (delete with no trash, a sent mail, an overwrite with no copy) → `irreversible`.
2. **Does it leave a trace even after undoing?** Notifications sent, history others see (created issues, an edited
   PR) → `partial`.
3. **Is there a real, tested command that undoes it?** Yes → `reversible_planned`, and pass it in `undo`.
   No → `reversible_manual` (moving 10 tickets back by hand).

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
- No jargon, flags, ids without a name, or command lines. Not «Ejecutar sync --apply».
- `summary` (≤ 6 rows) answers what a person would ask before clicking: how many, where, which ones, what remains.
- `detail` holds the full item list (folded). `risk_note` only when the default text per level says too little.
- `approve_label` with the count for batches: «Apruebo 11».

```json
{"skill": "drafts-cli", "consequence": "Vas a borrar tus 14 borradores de drafts-cli para siempre.",
 "reversibility": "irreversible", "audience": "me", "approve_label": "Apruebo 14",
 "summary": [["Borradores", "14"], ["Carpeta", "~/Library/Application Support/drafts-cli"]],
 "detail": ["Propuesta Q4", "Respuesta a Ana", "..."]}
```

## 4. Wire it

Build the JSON, find `awin` on the PATH, pass the JSON on stdin, branch on the exit code. Make the call injectable.

```python
import json, shutil, subprocess, sys

NO_AWIN = "drafts-cli: awin is not installed; install approval-window first"


def default_run_awin(request):
    """Run the real awin with the request on stdin; return its exit code."""
    exe = shutil.which("awin")
    if not exe:
        print(NO_AWIN, file=sys.stderr)
        return 3
    return subprocess.run([exe], input=json.dumps(request), universal_newlines=True).returncode


def cmd_purge(run_awin):
    drafts = load_drafts()
    if not drafts:
        print("nothing to purge")           # no window for a no-op
        return 0
    code = run_awin({...})                  # the request from step 3
    if code == 0:
        delete_all(drafts)                  # write ONLY here
        print("deleted %d drafts" % len(drafts))
        return 0
    if code == 1:
        print("not done: cancelled")
    elif code == 2:
        print("not done: invalid approval request (bug in drafts-cli)", file=sys.stderr)
    elif code == 3:
        print("not done: no approval window available on this machine", file=sys.stderr)
    else:
        print("not done: unexpected awin exit code %s" % code, file=sys.stderr)
    return code if code in (1, 2, 3) else 1


def main(argv, run_awin=None):
    run_awin = run_awin or default_run_awin
    ...
```

- Exit `0`: act. `1`: report "cancelled", write nothing, do not retry. `2`: a bug in your request; write nothing and
  fix the code. `3` or `awin` missing: refuse with a clear message; never fall back to writing without approval.
- **Never** add `--yes`, `--force`, an environment variable, a config flag, a pre-approval file or any other path that
  skips the window. Tests inject the call instead (step 5).
- Never answer, click or automate the window, and never retry after a cancel unless the person asks.
- When an agent runs the command, it tells the person first that a window will appear and what it asks.

Worked example in this repo: `approval-demo/demo.py` and its tests `tests/test_demo.py`.

## 5. Test it

Inject a fake `run_awin` that records requests and returns a fixed code. Never call the real `awin` from tests (a real
window would pop up).

```python
class Fake:
    def __init__(self, code):
        self.code, self.requests = code, []

    def __call__(self, request):
        self.requests.append(request)
        return self.code
```

Cover, for each action that asks:
- exit `0` writes; exits `1`, `2` and `3` leave the data untouched (compare the file before and after);
- exactly one request per command, with the expected `reversibility`, `audience` and counts in `consequence`;
- the commands that must not ask (read-only, additive, no-op) call the fake zero times;
- `default_run_awin` with `awin` missing from the PATH (`mock.patch("shutil.which", return_value=None)`) returns 3;
- the request is valid. With the approval-window repo importable, use its parser; otherwise check it against
  [references/protocol.md](references/protocol.md):

```python
try:
    from awin.request import parse          # approval-window repo on sys.path
except ImportError:
    parse = None

def assert_valid(self, request):
    if parse is None:
        self.skipTest("awin.request not importable; checked by hand against references/protocol.md")
    self.assertEqual(parse(request).warnings, ())   # raises InvalidRequest when invalid
```

If `awin` is installed, `$(dirname $(readlink ~/.local/bin/awin))` is the repo to put on `sys.path`.

## Checklist

- [ ] Only destructive, outward or shared writes ask; read-only, additive and no-op commands do not.
- [ ] One window per intent, before the first write, never in a loop.
- [ ] Level chosen by the three questions; `reversible_planned` only with a real, tested `undo`.
- [ ] `audience` set; `consequence` is «Vas a …» with numbers and names, ≤ 140 chars.
- [ ] Writes only on exit 0; refuses on 3 or missing `awin`; no bypass of any kind.
- [ ] Tests inject the call and prove no write on 1, 2 and 3.
