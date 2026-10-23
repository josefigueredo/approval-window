import contextlib
import io
import os
import subprocess
import unittest
from pathlib import Path

from awin import window
from awin.render import LEVEL_COLOR
from awin.request import parse

MIN = {
    "skill": "demo",
    "consequence": "Vas a borrar 3 notas",
    "reversibility": "irreversible",
    "audience": "me",
}


def build(**extra):
    with contextlib.redirect_stderr(io.StringIO()):
        return parse({**MIN, **extra})


class FakeRunner:
    def __init__(self, stdout="approved\n", returncode=0, raises=None):
        self.stdout, self.returncode, self.raises = stdout, returncode, raises
        self.argv = None
        self.kwargs = None
        self.page_seen = None

    def __call__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        self.page_seen = Path(argv[4]).read_text(encoding="utf-8")
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.avail = window.available
        window.available = lambda *a, **k: True

    def tearDown(self):
        window.available = self.avail

    def test_approved_only_on_exact_word(self):
        self.assertTrue(window.ask(build(), 60, FakeRunner("approved\n")))
        self.assertFalse(window.ask(build(), 60, FakeRunner("approved!\n")))
        self.assertFalse(window.ask(build(), 60, FakeRunner("")))

    def test_cancelled_is_false(self):
        self.assertFalse(window.ask(build(), 60, FakeRunner("cancelled\n")))

    def test_timeout_is_cancel(self):
        runner = FakeRunner(raises=subprocess.TimeoutExpired("osascript", 60))
        self.assertFalse(window.ask(build(), 60, runner))

    def test_osascript_failure_is_unavailable(self):
        with self.assertRaises(window.Unavailable):
            window.ask(build(), 60, FakeRunner("", returncode=1))

    def test_oserror_is_unavailable(self):
        with self.assertRaises(window.Unavailable):
            window.ask(build(), 60, FakeRunner(raises=OSError("boom")))

    def test_not_macos_is_unavailable(self):
        window.available = self.avail
        self.assertFalse(window.available(platform="linux"))
        self.assertFalse(window.available(platform="darwin", osascript="/nonexistent/osascript"))

    def test_ask_refuses_when_unavailable(self):
        window.available = lambda *a, **k: False
        runner = FakeRunner()
        with self.assertRaises(window.Unavailable):
            window.ask(build(), 60, runner)
        self.assertIsNone(runner.argv)

    def test_argv_shape(self):
        runner = FakeRunner()
        req = build(approve_label="Borro")
        window.ask(req, 42, runner)
        a = runner.argv
        self.assertEqual(a[:4], [window.OSASCRIPT, "-l", "JavaScript", str(window.WINDOW_JS)])
        self.assertEqual(a[5], "demo · Aprobación")
        self.assertEqual(a[6], "Borro")
        self.assertTrue(a[7].isdigit())
        self.assertEqual(len(a), 9)
        self.assertEqual(runner.kwargs["timeout"], 42)
        self.assertIn("<html", runner.page_seen.lower())

    def test_tint_only_for_tag_style(self):
        for level, color in LEVEL_COLOR.items():
            r = FakeRunner()
            window.ask(build(reversibility=level, undo="x", style="tag"), 60, r)
            self.assertEqual(r.argv[8], color)
        for style in ("alert", "edge"):
            r = FakeRunner()
            window.ask(build(style=style), 60, r)
            self.assertEqual(r.argv[8], "")

    def test_temp_page_is_removed(self):
        for runner in (FakeRunner(), FakeRunner(raises=subprocess.TimeoutExpired("o", 1)),
                       FakeRunner("", returncode=1)):
            try:
                window.ask(build(), 60, runner)
            except window.Unavailable:
                pass
            self.assertFalse(os.path.exists(runner.argv[4]))

    def test_default_timeout_is_max(self):
        self.assertEqual(window.MAX_TIMEOUT, 100)
        self.assertEqual(window.DEFAULT_TIMEOUT, window.MAX_TIMEOUT)

    def test_script_has_no_approve_shortcut(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        self.assertIn("ok.keyEquivalent = ''", src)
        self.assertIn("ok.enabled = false", src)
        self.assertEqual(src.count("NSBeep"), 1)
        self.assertNotIn("setDefaultButtonCell", src)
        self.assertNotIn("defaultButtonCell", src)
        self.assertNotIn("allowsContentJavaScript = true", src)
        # the only key equivalent assigned is Cancelar's Escape
        self.assertEqual(src.count("keyEquivalent ="), 2)


if __name__ == "__main__":
    unittest.main()
