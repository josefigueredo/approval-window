import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awin.request import parse

_cspec = importlib.util.spec_from_file_location(
    "check_request", Path(__file__).resolve().parent.parent / "references" / "check_request.py")
_checker = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(_checker)
check_request = _checker.check_request

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("demo", ROOT / "approval-demo" / "demo.py")
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)

EXPECTED = {
    "delete-note": ("irreversible", "alert", "me"),
    "share-note": ("partial", "tag", "external"),
    "rename-notes": ("reversible_manual", "edge", "me"),
    "archive-notes": ("reversible_planned", "alert", "me"),
    "unarchive-notes": ("reversible_planned", "edge", "me"),
    "reset": ("irreversible", "alert", "me"),
}


class Fake:
    def __init__(self, code):
        self.code, self.requests = code, []

    def __call__(self, request):
        self.requests.append(request)
        return self.code


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"APPROVAL_DEMO_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.file = Path(self.tmp.name) / "notes.json"

    def run_main(self, argv, run_awin):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = demo.main(argv, run_awin=run_awin)
        return code, out.getvalue(), err.getvalue()

    def notes(self):
        return json.loads(self.file.read_text(encoding="utf-8"))

    def test_first_use_creates_three_sample_notes(self):
        code, out, _ = self.run_main(["list"], Fake(0))
        self.assertEqual(code, 0)
        self.assertEqual(len(self.notes()), 3)
        self.assertEqual(len(out.strip().splitlines()), 3)

    def test_list_never_opens_a_window(self):
        fake = Fake(0)
        self.run_main(["list"], fake)
        self.assertEqual(fake.requests, [])

    def requests_for(self, action, code=1):
        fake = Fake(code)
        out = self.run_main([action], fake)
        return fake, out

    def test_every_request_is_valid_and_matches_the_brief(self):
        for action, (level, style, audience) in EXPECTED.items():
            with self.subTest(action=action):
                if action == "unarchive-notes":
                    self.run_main(["archive-notes"], Fake(0))
                fake, _ = self.requests_for(action)
                self.assertEqual(len(fake.requests), 1)
                check_request(fake.requests[0])
                req = parse(fake.requests[0])
                self.assertEqual(req.warnings, ())
                self.assertEqual(
                    (req.reversibility, req.style, req.audience), (level, style, audience))
                self.assertTrue(1 <= len(req.summary) <= 3)
        self.run_main(["unarchive-notes"], Fake(0))
        fake, _ = self.requests_for("archive-notes")
        self.assertEqual(fake.requests[0]["undo"], "demo.py unarchive-notes")
        self.run_main(["archive-notes"], Fake(0))
        fake, _ = self.requests_for("unarchive-notes")
        self.assertEqual(fake.requests[0]["undo"], "demo.py archive-notes")

    def test_approved_actions_change_the_file(self):
        self.run_main(["list"], Fake(0))
        before = self.notes()
        code, out, _ = self.run_main(["delete-note"], Fake(0))
        self.assertEqual(code, 0)
        self.assertEqual(len(self.notes()), len(before) - 1)
        self.assertEqual(len(out.strip().splitlines()), 1)

        self.run_main(["share-note"], Fake(0))
        self.assertTrue(any(n["shared"] for n in self.notes()))

        self.run_main(["rename-notes"], Fake(0))
        self.assertTrue(all(n["title"].startswith("[demo] ") for n in self.notes()))

        self.run_main(["archive-notes"], Fake(0))
        self.assertTrue(all(n["archived"] for n in self.notes()))
        self.run_main(["unarchive-notes"], Fake(0))
        self.assertFalse(any(n["archived"] for n in self.notes()))

    def test_cancel_exits_10_and_leaves_file_unchanged(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        for action in EXPECTED:
            if action == "unarchive-notes":
                continue  # nothing archived yet: no window (covered below)
            with self.subTest(action=action):
                code, out, err = self.run_main([action], Fake(1))
                self.assertEqual(code, demo.EXIT_CANCELLED)
                self.assertEqual(code, 10)
                self.assertEqual((out, err), ("not done: cancelled\n", ""))
                self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def assert_refused(self, awin_code, expected_exit, expected_err):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, out, err = self.run_main(["delete-note"], Fake(awin_code))
        self.assertEqual(code, expected_exit)
        self.assertEqual(out, "")
        self.assertEqual(err, expected_err + "\n")
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_invalid_awin_2_maps_to_70_not_usage(self):
        self.assert_refused(2, 70, "not done: invalid approval request (bug in approval-demo)")
        self.assertNotEqual(demo.EXIT_SOFTWARE, 2)

    def test_no_window_awin_3_maps_to_69(self):
        self.assert_refused(3, 69, demo.CANNOT_ASK)

    def test_unknown_exit_code_maps_to_70(self):
        for awin_code in (7, -9, 255):
            with self.subTest(awin_code=awin_code):
                self.assert_refused(awin_code, 70, "not done: unexpected awin exit code %s" % awin_code)

    def test_missing_awin_exits_69_with_exactly_one_message_and_no_write(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        with mock.patch.object(demo.shutil, "which", return_value=None), \
                mock.patch.object(demo.subprocess, "run") as run:
            code, out, err = self.run_main(["delete-note"], None)
        run.assert_not_called()
        self.assertEqual(code, 69)
        self.assertEqual(out, "")
        self.assertEqual(err, demo.CANNOT_ASK + "\n")
        self.assertIn("install.sh", demo.CANNOT_ASK)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_default_runner_is_silent_and_returns_3_when_awin_is_missing(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(demo.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(demo.default_run_awin({"skill": "x"}), 3)
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))

    def test_default_runner_oserror_is_cannot_ask(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        for exc in (PermissionError("denied"), FileNotFoundError("gone"), OSError("exec format")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(demo.shutil, "which", return_value="/x/awin"), \
                        mock.patch.object(demo.subprocess, "run", side_effect=exc):
                    self.assertEqual(demo.default_run_awin({"skill": "x"}), 3)
                    code, out, err = self.run_main(["delete-note"], None)
                self.assertEqual((code, out, err), (69, "", demo.CANNOT_ASK + "\n"))
                self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_default_runner_sends_json_on_stdin(self):
        with mock.patch.object(demo.shutil, "which", return_value="/x/awin"), \
                mock.patch.object(demo.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1)
            code, _, _ = self.run_main(["delete-note"], None)
        self.assertEqual(code, 10)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/x/awin"])
        self.assertEqual(json.loads(kwargs["input"])["reversibility"], "irreversible")

    def test_archive_asks_only_about_notes_not_yet_archived(self):
        self.run_main(["list"], Fake(0))
        notes = self.notes()
        notes[0]["archived"] = True
        self.file.write_text(json.dumps(notes), encoding="utf-8")
        fake, (code, _, _) = self.requests_for("archive-notes", 0)
        self.assertEqual(code, 0)
        self.assertIn("Vas a archivar 2 notas;", fake.requests[0]["consequence"])
        self.assertEqual(fake.requests[0]["summary"][0], ["Notas", "2"])
        self.assertNotIn(notes[0]["title"], fake.requests[0]["summary"][1][1])
        self.assertTrue(all(n["archived"] for n in self.notes()))

    def test_unarchive_asks_only_about_archived_notes(self):
        self.run_main(["list"], Fake(0))
        notes = self.notes()
        notes[1]["archived"] = True
        self.file.write_text(json.dumps(notes), encoding="utf-8")
        fake, (code, out, _) = self.requests_for("unarchive-notes", 0)
        self.assertEqual(code, 0)
        self.assertEqual(fake.requests[0]["consequence"], "Vas a restaurar 1 nota archivada.")
        self.assertEqual(fake.requests[0]["summary"][1], ["Títulos", notes[1]["title"]])
        self.assertIn("unarchived 1 note\n", out)

    def test_no_op_actions_open_no_window(self):
        self.run_main(["list"], Fake(0))
        for action in ("unarchive-notes",):
            fake, (code, out, _) = self.requests_for(action, 0)
            self.assertEqual((code, fake.requests), (0, []))
            self.assertIn("nothing to do", out)
        self.run_main(["archive-notes"], Fake(0))
        fake, (code, out, _) = self.requests_for("archive-notes", 0)
        self.assertEqual((code, fake.requests), (0, []))
        self.assertIn("nothing to do", out)
        self.file.write_text("[]", encoding="utf-8")
        for action in ("delete-note", "share-note", "rename-notes", "archive-notes", "unarchive-notes"):
            with self.subTest(action=action):
                fake, (code, out, _) = self.requests_for(action, 0)
                self.assertEqual((code, fake.requests), (0, []))
                self.assertIn("nothing to do", out)

    def test_wording_is_count_aware(self):
        one = [dict(demo.SAMPLE[0])]
        self.run_main(["list"], Fake(0))
        self.file.write_text(json.dumps(one), encoding="utf-8")
        cases = {
            "rename-notes": ("Vas a renombrar 1 nota agregando", "renamed 1 note\n"),
            "archive-notes": ("Vas a archivar 1 nota; deja de verse", "archived 1 note\n"),
            "unarchive-notes": ("Vas a restaurar 1 nota archivada.", "unarchived 1 note\n"),
            "reset": ("Vas a reemplazar tu nota por las 3 de ejemplo.", "restored 3 sample notes\n"),
        }
        for action, (phrase, result) in cases.items():
            with self.subTest(action=action):
                self.file.write_text(json.dumps(one), encoding="utf-8")
                if action == "unarchive-notes":
                    self.run_main(["archive-notes"], Fake(0))
                fake, (code, out, _) = self.requests_for(action, 0)
                self.assertEqual(code, 0)
                self.assertIn(phrase, fake.requests[0]["consequence"])
                self.assertTrue(out.endswith(result), out)
                check_request(fake.requests[0])
        self.file.write_text(json.dumps([dict(n) for n in demo.SAMPLE]), encoding="utf-8")
        fake, (_, out, _) = self.requests_for("rename-notes", 0)
        self.assertIn("Vas a renombrar 3 notas agregando", fake.requests[0]["consequence"])
        self.assertTrue(out.endswith("renamed 3 notes\n"))
        self.run_main(["archive-notes"], Fake(1))
        fake, _ = self.requests_for("archive-notes")
        self.assertIn("Vas a archivar 3 notas; dejan de verse", fake.requests[0]["consequence"])
        for request in fake.requests:
            for text in [request["consequence"]] + [v for _, v in request.get("summary", [])]:
                self.assertNotRegex(text, r"\b1 notas\b|\btus [01] notas\b|\b0 notas\b")

    def test_bad_usage_exits_2(self):
        for argv in ([], ["nope"], ["list", "x"]):
            code, _, err = self.run_main(argv, Fake(0))
            self.assertEqual(code, 2)
            self.assertIn("usage", err)

    def test_reset_approved_restores_sample_notes_even_when_empty(self):
        self.run_main(["list"], Fake(0))
        self.file.write_text("[]", encoding="utf-8")
        fake = Fake(0)
        code, _, _ = self.run_main(["reset"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(self.notes(), demo.SAMPLE)
        self.assertEqual(fake.requests[0]["consequence"],
                         "Vas a reemplazar tu lista vacía por las 3 notas de ejemplo.")
        check_request(fake.requests[0])

    def test_reset_cancelled_leaves_notes_unchanged(self):
        self.run_main(["delete-note"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, _, _ = self.run_main(["reset"], Fake(1))
        self.assertEqual(code, 10)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_skill_md_names_the_real_buttons_and_codes(self):
        text = (ROOT / "approval-demo" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("«Apruebo»", text)
        self.assertIn("«Cancelar»", text)
        self.assertNotRegex(text, r"\bApprove\b|\bCancel\b")
        for code in ("10", "69", "70"):
            self.assertIn("`%s`" % code, text)

    def test_no_bypass_option_exists(self):
        code, _, _ = self.run_main(["delete-note", "--yes"], Fake(0))
        self.assertEqual(code, 2)


class SkillFrontmatterTest(unittest.TestCase):
    """Strict YAML parsers (Copilot CLI) reject what Claude Code tolerates."""

    def test_frontmatter_values_are_plain_yaml_scalars(self):
        for path in (ROOT / "SKILL.md", ROOT / "approval-demo" / "SKILL.md"):
            lines = path.read_text(encoding="utf-8").split("\n")
            self.assertEqual(lines[0], "---", path)
            end = lines.index("---", 1)
            for line in lines[1:end]:
                key, sep, value = line.partition(": ")
                self.assertTrue(sep, "%s: bad line %r" % (path, line))
                with self.subTest(path=path.name, key=key):
                    self.assertNotIn(": ", value)
                    self.assertNotIn(" #", value)
                    self.assertNotIn(value[:1], "\"'[]{}&*!|>%@`#,?-")


if __name__ == "__main__":
    unittest.main()
