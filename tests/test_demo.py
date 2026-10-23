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

    def test_every_request_is_valid_and_matches_the_brief(self):
        for action, (level, style, audience) in EXPECTED.items():
            with self.subTest(action=action):
                fake = Fake(1)
                self.run_main([action], fake)
                self.assertEqual(len(fake.requests), 1)
                req = parse(fake.requests[0])
                self.assertEqual(
                    (req.reversibility, req.style, req.audience), (level, style, audience))
                self.assertTrue(1 <= len(req.summary) <= 3)
        fake = Fake(1)
        self.run_main(["archive-notes"], fake)
        self.assertEqual(fake.requests[0]["undo"], "demo.py unarchive-notes")
        fake = Fake(1)
        self.run_main(["unarchive-notes"], fake)
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

    def test_cancel_exit_1_leaves_file_unchanged(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        for action in EXPECTED:
            code, out, _ = self.run_main([action], Fake(1))
            self.assertEqual(code, 1)
            self.assertIn("not done: cancelled", out)
            self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_invalid_exit_2_and_no_write(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, out, _ = self.run_main(["delete-note"], Fake(2))
        self.assertEqual(code, 2)
        self.assertIn("not done: the request was invalid (bug in approval-demo)", out)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_no_window_exit_3_refuses_and_no_write(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, out, err = self.run_main(["delete-note"], Fake(3))
        self.assertEqual(code, 3)
        self.assertIn("not done", out + err)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_unknown_exit_code_is_not_an_approval(self):
        self.run_main(["list"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, _, _ = self.run_main(["delete-note"], Fake(7))
        self.assertNotEqual(code, 0)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

    def test_missing_awin_exits_3_with_message_and_no_write(self):
        with mock.patch.object(demo.shutil, "which", return_value=None), \
                mock.patch.object(demo.subprocess, "run") as run:
            code, _, err = self.run_main(["delete-note"], None)
        run.assert_not_called()
        self.assertEqual(code, 3)
        self.assertIn(
            "approval-demo: awin is not installed; run install.sh from the approval-window repo", err)
        self.assertFalse(self.file.exists() and len(self.notes()) != 3)

    def test_default_runner_sends_json_on_stdin(self):
        with mock.patch.object(demo.shutil, "which", return_value="/x/awin"), \
                mock.patch.object(demo.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1)
            code, _, _ = self.run_main(["delete-note"], None)
        self.assertEqual(code, 1)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/x/awin"])
        self.assertEqual(json.loads(kwargs["input"])["reversibility"], "irreversible")

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
        self.assertIn("0 notas", fake.requests[0]["consequence"])

    def test_reset_cancelled_leaves_notes_unchanged(self):
        self.run_main(["delete-note"], Fake(0))
        raw = self.file.read_text(encoding="utf-8")
        code, _, _ = self.run_main(["reset"], Fake(1))
        self.assertEqual(code, 1)
        self.assertEqual(self.file.read_text(encoding="utf-8"), raw)

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
