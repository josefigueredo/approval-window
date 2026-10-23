import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("notes", HERE / "notes.py")
notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notes)


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"NOTES_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.file = Path(self.tmp.name) / "notes.json"

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = notes.main(argv)
        return code, out.getvalue(), err.getvalue()

    def stored(self):
        return json.loads(self.file.read_text(encoding="utf-8"))

    def test_add_appends_a_note(self):
        self.run_main(["add", "buy milk"])
        code, out, _ = self.run_main(["add", "call Ana"])
        self.assertEqual(code, 0)
        self.assertEqual(self.stored(), ["buy milk", "call Ana"])
        self.assertIn("added note 2", out)

    def test_add_joins_words(self):
        self.run_main(["add", "buy", "milk"])
        self.assertEqual(self.stored(), ["buy milk"])

    def test_list_prints_notes(self):
        self.run_main(["add", "buy milk"])
        code, out, _ = self.run_main(["list"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "1. buy milk\n")

    def test_list_without_file_writes_nothing(self):
        code, out, _ = self.run_main(["list"])
        self.assertEqual((code, out), (0, ""))
        self.assertFalse(self.file.exists())

    def test_clear_deletes_every_note(self):
        self.run_main(["add", "a"])
        self.run_main(["add", "b"])
        code, out, _ = self.run_main(["clear"])
        self.assertEqual(code, 0)
        self.assertEqual(self.stored(), [])
        self.assertIn("deleted 2 notes", out)

    def test_clear_with_no_notes_is_a_no_op(self):
        code, out, _ = self.run_main(["clear"])
        self.assertEqual(code, 0)
        self.assertIn("nothing to clear", out)
        self.assertFalse(self.file.exists())

    def test_bad_arguments_print_usage(self):
        for argv in ([], ["add"], ["clear", "x"], ["drop"]):
            code, _, err = self.run_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("usage:", err)

    def test_default_home(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(notes.data_file(),
                             Path.home() / ".local" / "state" / "notes-cli" / "notes.json")


if __name__ == "__main__":
    unittest.main()
