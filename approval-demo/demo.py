#!/usr/bin/env python3
"""approval-demo: fake note actions, one per reversibility level, to try awin.

Every action asks `awin` first and writes only when it exits 0.
Stdlib only, Python 3.9 compatible.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = "approval-demo"
ACTIONS = ("delete-note", "share-note", "rename-notes", "archive-notes", "unarchive-notes", "reset")
SAMPLE = [
    {"id": 1, "title": "Shopping list", "archived": False, "shared": False},
    {"id": 2, "title": "Meeting notes", "archived": False, "shared": False},
    {"id": 3, "title": "Ideas", "archived": False, "shared": False},
]
NO_AWIN = "approval-demo: awin is not installed; run install.sh from the approval-window repo"


def data_file():
    home = os.environ.get("APPROVAL_DEMO_HOME")
    base = Path(home) if home else Path.home() / ".local" / "state" / "approval-demo"
    return base / "notes.json"


def load():
    path = data_file()
    if not path.exists():
        save([dict(n) for n in SAMPLE])
    return json.loads(path.read_text(encoding="utf-8"))


def save(notes):
    path = data_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def titles(notes):
    return ", ".join(n["title"] for n in notes)


def _request(**kw):
    kw["skill"] = SKILL
    return kw


def plan_delete(notes):
    if not notes:
        return None
    note = notes[0]
    req = _request(
        consequence='Vas a borrar la nota "%s" para siempre.' % note["title"][:60],
        reversibility="irreversible", audience="me", style="alert",
        summary=[["Nota", note["title"]], ["Notas que quedan", str(len(notes) - 1)]])

    def apply():
        save(notes[1:])
        return 'deleted note "%s"' % note["title"]
    return req, apply


def plan_share(notes):
    if not notes:
        return None
    note = notes[0]
    req = _request(
        consequence='Vas a compartir la nota "%s" con gente de afuera.' % note["title"][:60],
        reversibility="partial", audience="external", style="tag",
        summary=[["Nota", note["title"]], ["Destino", "enlace público"]])

    def apply():
        note["shared"] = True
        save(notes)
        return 'shared note "%s"' % note["title"]
    return req, apply


def plan_rename(notes):
    if not notes:
        return None
    req = _request(
        consequence="Vas a renombrar %d notas agregando el prefijo [demo]." % len(notes),
        reversibility="reversible_manual", audience="me", style="edge",
        summary=[["Notas", str(len(notes))], ["Prefijo", "[demo] "]])

    def apply():
        for n in notes:
            if not n["title"].startswith("[demo] "):
                n["title"] = "[demo] " + n["title"]
        save(notes)
        return "renamed %d notes" % len(notes)
    return req, apply


def plan_archive(notes):
    todo = notes
    if not todo:
        return None
    req = _request(
        consequence="Vas a archivar %d notas; dejan de verse en la lista." % len(todo),
        reversibility="reversible_planned", audience="me", style="alert",
        undo="demo.py unarchive-notes",
        summary=[["Notas", str(len(todo))], ["Títulos", titles(todo)[:100]]])

    def apply():
        for n in todo:
            n["archived"] = True
        save(notes)
        return "archived %d notes" % len(todo)
    return req, apply


def plan_unarchive(notes):
    todo = notes
    if not todo:
        return None
    req = _request(
        consequence="Vas a restaurar %d notas archivadas." % len(todo),
        reversibility="reversible_planned", audience="me", style="edge",
        undo="demo.py archive-notes",
        summary=[["Notas", str(len(todo))], ["Títulos", titles(todo)[:100]]])

    def apply():
        for n in todo:
            n["archived"] = False
        save(notes)
        return "unarchived %d notes" % len(todo)
    return req, apply


def plan_reset(notes):
    req = _request(
        consequence="Vas a reemplazar tus %d notas por las %d de ejemplo." % (len(notes), len(SAMPLE)),
        reversibility="irreversible", audience="me", style="alert",
        summary=[["Notas actuales", str(len(notes))], ["Notas de ejemplo", str(len(SAMPLE))]])

    def apply():
        save([dict(n) for n in SAMPLE])
        return "restored %d sample notes" % len(SAMPLE)
    return req, apply


PLANS = {
    "reset": plan_reset,
    "delete-note": plan_delete,
    "share-note": plan_share,
    "rename-notes": plan_rename,
    "archive-notes": plan_archive,
    "unarchive-notes": plan_unarchive,
}


def default_run_awin(request):
    """Run the real awin with the request on stdin; return its exit code."""
    exe = shutil.which("awin")
    if not exe:
        print(NO_AWIN, file=sys.stderr)
        return 3
    return subprocess.run([exe], input=json.dumps(request), universal_newlines=True).returncode


def usage():
    print("usage: demo.py list | %s" % " | ".join(ACTIONS), file=sys.stderr)
    return 2


def main(argv, run_awin=None):
    if len(argv) != 1 or (argv[0] != "list" and argv[0] not in PLANS):
        return usage()
    notes = load()
    if argv[0] == "list":
        for n in notes:
            flags = "".join(f for f, on in (("A", n["archived"]), ("S", n["shared"])) if on)
            print("%d. %s%s" % (n["id"], n["title"], " [%s]" % flags if flags else ""))
        return 0
    plan = PLANS[argv[0]](notes)
    if plan is None:
        print("nothing to do: no matching notes")
        return 0
    request, apply = plan
    code = (run_awin or default_run_awin)(request)
    if code == 0:
        print("done: " + apply())
        return 0
    if code == 1:
        print("not done: cancelled")
    elif code == 2:
        print("not done: the request was invalid (bug in approval-demo)")
    elif code == 3:
        print("not done: no approval window available on this machine")
    else:
        print("not done: unexpected awin exit code %s" % code)
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
