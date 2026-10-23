import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awin import __version__, window
from awin.cli import main

ROOT = Path(__file__).resolve().parent.parent
MIN = {
    "skill": "demo",
    "consequence": "Vas a borrar 3 notas",
    "reversibility": "irreversible",
    "audience": "me",
}


class Asker:
    def __init__(self, result=True, raises=None):
        self.result, self.raises = result, raises
        self.calls = []

    def __call__(self, req, timeout):
        self.calls.append((req, timeout))
        if self.raises:
            raise self.raises
        return self.result


def run(argv=(), data=None, raw=None, asker=None, available=True):
    if raw is None:
        raw = json.dumps(data if data is not None else MIN).encode()
    out, err = io.StringIO(), io.StringIO()
    asker = asker or Asker()
    code = main(list(argv), stdin=io.BytesIO(raw), stdout=out, stderr=err,
                asker=asker, is_available=lambda: available)
    return code, out.getvalue(), err.getvalue(), asker


class CliTest(unittest.TestCase):
    def test_approved_exit_0_and_word(self):
        code, out, err, asker = run(asker=Asker(True))
        self.assertEqual((code, out, err), (0, "approved\n", ""))
        self.assertEqual(len(asker.calls), 1)
        self.assertEqual(asker.calls[0][1], window.DEFAULT_TIMEOUT)

    def test_cancelled_exit_1(self):
        code, out, err, _ = run(asker=Asker(False))
        self.assertEqual((code, out, err), (1, "cancelled\n", ""))

    def test_invalid_input_exit_2_no_window(self):
        for raw in (b"", b"{", b"[]", b"\xff", b'{"approved": true}'):
            with self.subTest(raw=raw):
                code, out, err, asker = run(raw=raw)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertTrue(err.startswith("awin: "))
                self.assertEqual(err.count("\n"), 1)
                self.assertEqual(asker.calls, [])

    def test_extra_approval_keys_rejected(self):
        for key in ("approved", "yes"):
            code, _, _, asker = run(data={**MIN, key: True})
            self.assertEqual(code, 2)
            self.assertEqual(asker.calls, [])

    def test_unavailable_exit_3(self):
        code, out, err, asker = run(available=False)
        self.assertEqual((code, out), (3, ""))
        self.assertTrue(err.startswith("awin: "))
        self.assertEqual(asker.calls, [])
        code, out, err, _ = run(asker=Asker(raises=window.Unavailable("osascript failed")))
        self.assertEqual((code, out), (3, ""))
        self.assertIn("osascript failed", err)

    def test_invalid_input_wins_over_unavailable(self):
        code, _, _, _ = run(raw=b"{", available=False)
        self.assertEqual(code, 2)

    def test_spec_file_option(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "spec.json")
            Path(path).write_text(json.dumps({**MIN, "consequence": "Desde archivo"}))
            code, out, _, asker = run(["--spec", path], raw=b"{")
            self.assertEqual((code, out), (0, "approved\n"))
            self.assertEqual(asker.calls[0][0].consequence, "Desde archivo")
            code, out, err, asker = run(["--spec", os.path.join(d, "nope.json")])
            self.assertEqual((code, out), (2, ""))
            self.assertTrue(err.startswith("awin: "))
            self.assertEqual(asker.calls, [])

    def test_timeout_can_only_lower(self):
        code, _, _, asker = run(["--timeout", "30"])
        self.assertEqual((code, asker.calls[0][1]), (0, 30))
        code, _, _, asker = run(["--timeout", str(window.MAX_TIMEOUT)])
        self.assertEqual((code, asker.calls[0][1]), (0, window.MAX_TIMEOUT))
        for bad in ("9999", str(window.MAX_TIMEOUT + 1), "0", "-5", "abc"):
            with self.subTest(timeout=bad):
                code, out, err, asker = run(["--timeout", bad])
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("awin: "))
                self.assertEqual(asker.calls, [])

    def test_unknown_option_exit_2(self):
        for argv in (["--yes"], ["--approve"], ["extra"]):
            code, out, _, asker = run(argv)
            self.assertEqual((code, out, asker.calls), (2, "", []))

    def test_no_approval_shortcut_exists(self):
        from awin.cli import build_parser
        flags = {f for a in build_parser()._actions for f in a.option_strings}
        self.assertEqual(flags, {"-h", "--help", "--spec", "--timeout", "--version"})

    def test_warnings_go_to_stderr(self):
        code, out, err, asker = run(data={**MIN, "reversibility": "reversible_planned"})
        line = "awin: reversible_planned without undo; shown as reversible_manual\n"
        self.assertEqual(err.count(line), 1)
        self.assertEqual((code, out), (0, "approved\n"))
        self.assertEqual(len(asker.calls), 1)

    def test_version(self):
        code, out, _, asker = run(["--version"], raw=b"")
        self.assertEqual(code, 0)
        self.assertIn(__version__, out)
        self.assertEqual(asker.calls, [])

    def test_help_exit_0(self):
        code, out, _, _ = run(["-h"], raw=b"")
        self.assertEqual(code, 0)
        self.assertIn("usage", out)


class SmokeTest(unittest.TestCase):
    def run_script(self, script, *args, stdin=b""):
        return subprocess.run([sys.executable, str(script), *args], input=stdin,
                              capture_output=True, timeout=30)

    def test_executable_with_shebang(self):
        script = ROOT / "awin.py"
        self.assertTrue(os.access(script, os.X_OK))
        self.assertEqual(script.read_text().splitlines()[0], "#!/usr/bin/env python3")

    def test_version_subprocess(self):
        r = self.run_script(ROOT / "awin.py", "--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn(__version__, r.stdout.decode())

    def test_invalid_input_subprocess(self):
        r = self.run_script(ROOT / "awin.py", stdin=b"{")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b"")
        self.assertTrue(r.stderr.startswith(b"awin: "))

    def test_works_through_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "awin"
            link.symlink_to(ROOT / "awin.py")
            r = self.run_script(link, "--version")
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
