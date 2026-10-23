# Wiring and testing awin in a CLI

Details behind steps 3–5 of the skill. Everything here is stdlib Python 3.9+.

## Building the request

Count-aware wording: one item and many items read differently in Spanish. Never send «Vas a borrar tus 1 notas».

```python
def count_phrase(n, one, many):
    """count_phrase(1, "tu nota", "tus {n} notas") -> "tu nota"; with 3 -> "tus 3 notas"."""
    return one if n == 1 else many.format(n=n)


def cut(text, limit):
    """Cut text to the protocol limit, marking the cut."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def purge_request(drafts):
    n = len(drafts)
    return {
        "skill": "drafts-cli",
        "consequence": cut("Vas a borrar %s para siempre." % count_phrase(n, "tu borrador", "tus {n} borradores"), 140),
        "reversibility": "irreversible",
        "audience": "me",
        "approve_label": "Apruebo %d" % n if n > 1 else "Apruebo",
        "summary": [["Borradores", str(n)], ["Primero", cut(drafts[0].title, 100)]],
        "detail": [cut(d.title, 300) for d in drafts],
    }
```

Limits to respect before sending (awin rejects with exit 2 otherwise): `consequence` ≤ 140, `summary` ≤ 6 rows with
label 1–30 and value ≤ 100, `detail` lines ≤ 300 (more than 200 lines is fine: awin truncates). Names that come from
the person's data (titles, paths) are the usual offenders: cut them.

## Exit codes of your CLI

awin's codes are **awin's**, not your CLI's. Map them; never pass them straight through when they collide with your
own codes (most CLIs already use 2 for a usage error). Pick codes, document them in the CLI's usage or README, and test
them. A mapping that avoids the common ones:

| awin | Means | Your CLI prints (one line) | Your CLI exits |
|---|---|---|---|
| 0 | approved | the result of the action | 0 |
| 1 | cancelled, closed, timed out | `not done: cancelled` | e.g. 10 (`EXIT_CANCELLED`) |
| 2 | your request was invalid | `not done: invalid approval request (bug in <cli>)` | e.g. 70 (`EXIT_SOFTWARE`, sysexits) |
| 3, or awin missing | no window can be shown | `not done: cannot ask for approval; needs macOS and awin (install approval-window)` | e.g. 69 (`EXIT_UNAVAILABLE`, sysexits) |
| other | unexpected | `not done: unexpected awin exit code N` | 70 |

When awin is missing, print **one** message. `default_run_awin` returns 3 silently and the code-3 branch prints the
single message that says what to install; do not print in both places. The same goes for an `awin` that is on the PATH
but cannot start: catch `OSError` around `subprocess.run` and return 3, so it is "cannot ask", never a traceback.

## Updating existing tests

Adding the seam changes `main`'s signature to `main(argv, run_awin=None)`, and `None` means "the real awin". Every
existing test that calls `main` for a command that now asks must inject a fake, or it would open a real window. Make
the fake default to **cancelled** so a forgotten case writes nothing and never reaches awin:

```python
class Fake:
    def __init__(self, code=1):              # default: cancelled
        self.code, self.requests = code, []

    def __call__(self, request):
        self.requests.append(request)
        return self.code
```

Pass it in every call (`notes.main(argv, run_awin=Fake())`), also for commands that must not ask, and assert
`fake.requests == []` there. Use `Fake(0)` only in the tests that check the write.

## Validating the request in tests

Copy `references/check_request.py` (stdlib, no dependency) into your tests and call `check_request(request)` on every
request your fake recorded. It enforces the protocol plus «Vas a …» and `undo` for `reversible_planned`. When the
approval-window repo is importable, also run the real parser; it is stricter, never a replacement for the copy:

```python
try:
    from awin.request import parse           # approval-window repo on sys.path
except ImportError:
    parse = None

def assert_valid(self, request):
    check_request(request)                    # always
    if parse is not None:
        self.assertEqual(parse(request).warnings, ())
```

The repo is `$(dirname "$(readlink ~/.local/bin/awin)")` when awin is installed.

## The worked example

`approval-demo/demo.py` and `tests/test_demo.py` inside the approval-window repo:
`$(dirname "$(readlink ~/.local/bin/awin)")/approval-demo/demo.py`. It has one action per level, the injected
`run_awin`, a write only on exit 0, and tests for 1, 2 and 3. Reading it is optional; the pattern is the one above.
