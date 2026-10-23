#!/usr/bin/env python3
"""notes-cli: a tiny note keeper.

Notes are a JSON list of strings in $NOTES_HOME/notes.json
(default ~/.local/state/notes-cli/notes.json).
Stdlib only, Python 3.9 compatible.
"""
import json
import os
import sys
from pathlib import Path

USAGE = "usage: notes.py add <text> | list | clear"


def data_file():
    home = os.environ.get("NOTES_HOME")
    base = Path(home) if home else Path.home() / ".local" / "state" / "notes-cli"
    return base / "notes.json"


def load():
    path = data_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(notes):
    path = data_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_add(words):
    notes = load()
    notes.append(" ".join(words))
    save(notes)
    print("added note %d" % len(notes))
    return 0


def cmd_list():
    for i, text in enumerate(load(), 1):
        print("%d. %s" % (i, text))
    return 0


def cmd_clear():
    notes = load()
    if not notes:
        print("nothing to clear")
        return 0
    save([])
    print("deleted %d notes" % len(notes))
    return 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "add":
        return cmd_add(argv[1:])
    if argv == ["list"]:
        return cmd_list()
    if argv == ["clear"]:
        return cmd_clear()
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
