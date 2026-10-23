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

    def _method(self, src, selector):
        """The body of one delegate method in window.js, up to the next method."""
        start = src.index("'%s': {" % selector)
        end = src.find("\n    '", start + 1)
        return src[start:end if end != -1 else len(src)]

    def test_script_refuses_an_unreadable_page_file(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        # JXA wraps nil in an object, so `!html` alone is never true and a missing file opened a window (measured
        # 2026-10-23): the guard has to ask isNil().
        self.assertIn("if (!html || html.isNil())", src)

    def test_script_blocks_navigation_it_did_not_start(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        # JXA cannot call a WebKit block, and declaring decidePolicy under WKNavigationDelegate kills osascript
        # (-2700, measured 2026-10-23): no policy delegate at all.
        self.assertNotIn("decidePolicy", src)
        self.assertNotIn("decisionHandler", src)
        self.assertIn("protocols: ['WKNavigationDelegate', 'WKUIDelegate']", src)
        # dropping a file is what could navigate: the web view accepts no drags
        self.assertIn("web.unregisterDraggedTypes;", src)
        self.assertLess(src.index("initWithFrameConfiguration"), src.index("web.unregisterDraggedTypes;"))
        # every load awin starts goes through loadPage, which counts it
        self.assertEqual(src.count("loadHTMLStringBaseURL"), 1)
        load = src[src.index("function loadPage"):]
        self.assertLess(load.index("expectedLoads += 1"), load.index("loadHTMLStringBaseURL"))
        # a navigation that starts without being counted taints the page: Apruebo never enables again
        start = self._method(src, "webView:didStartProvisionalNavigation:")
        self.assertIn("tainted = true", start)
        self.assertIn("ok.enabled = false", start)
        self.assertIn("generation += 1", start)
        # no link opens anything: the page has no links (every caller string is escaped text)
        create = self._method(src, "webView:createWebViewWithConfiguration:forNavigationAction:windowFeatures:")
        self.assertNotIn("openURL", src)
        self.assertNotIn("'https'", src)
        self.assertIn("return $();", create)

    def test_script_invalidates_a_pending_enable_timer(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        self.assertIn("function cancelEnable()", src)
        cancel = src[src.index("function cancelEnable()"):]
        cancel = cancel[:cancel.index("\n}\n")]
        self.assertIn("enableTimer.invalidate", cancel)
        self.assertIn("enableTimer = null", cancel)
        for selector in ("webView:didStartProvisionalNavigation:", "webViewWebContentProcessDidTerminate:",
                         "webView:didFinishNavigation:"):
            with self.subTest(selector=selector):
                self.assertIn("cancelEnable();", self._method(src, selector))
        finish = self._method(src, "webView:didFinishNavigation:")
        self.assertIn("enableTimer = $.NSTimer.timerWithTimeIntervalTargetSelectorUserInfoRepeats", finish)
        enable = self._method(src, "enableApprove:")
        self.assertIn("enableTimer = null", enable)

    def test_script_enables_approve_only_after_a_delay_in_the_modal_run_loop(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        finish = self._method(src, "webView:didFinishNavigation:")
        self.assertNotIn("ok.enabled = true", finish)
        self.assertIn("APPROVE_DELAY", finish)
        self.assertIn("const APPROVE_DELAY = 0.7;", src)
        self.assertIn("timerWithTimeIntervalTargetSelectorUserInfoRepeats(APPROVE_DELAY", finish)
        # runModalForWindow runs NSModalPanelRunLoopMode: a default-mode timer would never fire
        self.assertIn("addTimerForMode(enableTimer, $.NSRunLoopCommonModes)", finish)
        self.assertIn("$.NSRunLoopCommonModes", finish)
        self.assertNotIn("afterDelay", src)
        self.assertNotIn("scheduledTimer", src)
        enable = self._method(src, "enableApprove:")
        self.assertIn("armed === generation", enable)
        self.assertIn("!tainted", enable)
        self.assertEqual(src.count("ok.enabled = true"), 1)
        died = self._method(src, "webViewWebContentProcessDidTerminate:")
        self.assertIn("generation += 1", died)
        self.assertIn("ok.enabled = false", died)

    def test_script_has_no_approve_shortcut(self):
        src = window.WINDOW_JS.read_text(encoding="utf-8")
        self.assertIn("ok.keyEquivalent = ''", src)
        self.assertIn("ok.refusesFirstResponder = true;", src)
        self.assertIn("ok.enabled = false", src)
        self.assertEqual(src.count("NSBeep"), 1)
        self.assertNotIn("CGColor", src)
        self.assertNotIn(".layer.", src)
        self.assertNotIn("setDefaultButtonCell", src)
        self.assertNotIn("defaultButtonCell", src)
        self.assertNotIn("allowsContentJavaScript = true", src)
        # the only key equivalent assigned is Cancelar's Escape
        self.assertEqual(src.count("keyEquivalent ="), 2)


if __name__ == "__main__":
    unittest.main()
