"""Checks on the approval-window skill: frontmatter, links, and that every example request is valid."""
import contextlib
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path

from awin.request import InvalidRequest, parse

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
DOCS = (SKILL, ROOT / "references" / "protocol.md", ROOT / "references" / "choosing-a-level.md",
        ROOT / "references" / "wiring.md")
CHECKER = ROOT / "references" / "check_request.py"
JSON_BLOCK = re.compile(r"```json\n(.*?)```", re.S)


def frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    return dict(line.split(": ", 1) for line in match.group(1).splitlines())


class SkillTest(unittest.TestCase):
    def test_frontmatter(self):
        meta = frontmatter(SKILL.read_text(encoding="utf-8"))
        self.assertEqual(meta.get("name"), "approval-window")
        self.assertTrue(meta.get("description", "").startswith(
            "Use when building or changing a skill's CLI that performs an action with effects outside the process"))
        self.assertIn("read-only", meta["description"])

    def test_linked_files_exist(self):
        text = SKILL.read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)#:]+)\)", text)
        self.assertIn("references/protocol.md", links)
        self.assertIn("references/choosing-a-level.md", links)
        for link in links:
            self.assertTrue((ROOT / link).exists(), link)

    def test_every_json_example_is_a_valid_request_without_downgrade(self):
        count = 0
        for doc in DOCS:
            for block in JSON_BLOCK.findall(doc.read_text(encoding="utf-8")):
                count += 1
                with self.subTest(doc=doc.name, block=block[:60]):
                    err = io.StringIO()
                    with contextlib.redirect_stderr(err):
                        request = parse(json.loads(block))
                    self.assertEqual(request.warnings, ())
                    self.assertTrue(request.consequence.startswith("Vas a "), request.consequence)
        self.assertGreaterEqual(count, 4)

    def test_never_teaches_a_bypass(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("--yes", text)  # named only to forbid it
        self.assertNotRegex(text, r"add_argument\(\s*['\"]--(yes|force|no-confirm)")


    def test_validation_pattern_never_skips(self):
        for doc in DOCS:
            self.assertNotIn("skipTest", doc.read_text(encoding="utf-8"), doc.name)


def load_checker():
    spec = importlib.util.spec_from_file_location("check_request", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check_request


GOOD = {"skill": "drafts-cli", "consequence": "Vas a borrar tus 3 borradores para siempre.",
        "reversibility": "irreversible", "audience": "me"}
BAD = [
    {k: v for k, v in GOOD.items() if k != "audience"},
    dict(GOOD, yes=True),
    dict(GOOD, reversibility="maybe"),
    dict(GOOD, audience="everyone"),
    dict(GOOD, style="loud"),
    dict(GOOD, consequence="x" * 141),
    dict(GOOD, consequence=""),
    dict(GOOD, skill="s" * 41),
    dict(GOOD, summary=[["a", "b"]] * 7),
    dict(GOOD, summary=[["a", "b" * 101]]),
    dict(GOOD, summary=[["", "b"]]),
    dict(GOOD, detail=["x" * 301]),
    dict(GOOD, approve_label="A" * 25),
    dict(GOOD, risk_note="r" * 141),
    dict(GOOD, undo="u" * 201),
]


class CheckerTest(unittest.TestCase):
    """references/check_request.py is the stdlib check consumers copy; it must agree with awin's parser."""

    def setUp(self):
        self.check = load_checker()

    def test_accepts_a_valid_request(self):
        self.check(GOOD)
        self.check(dict(GOOD, reversibility="reversible_planned", undo="drafts-cli restore",
                        summary=[["Borradores", "3"]], detail=["a"], style="edge", approve_label="Apruebo 3"))

    def test_rejects_what_awin_rejects(self):
        for request in BAD:
            with self.subTest(request=str(request)[:80]):
                with self.assertRaises(InvalidRequest):
                    parse(request)
                with self.assertRaises(AssertionError):
                    self.check(request)

    def test_rejects_planned_without_undo_and_consequence_without_vas_a(self):
        for request in (dict(GOOD, reversibility="reversible_planned"),
                        dict(GOOD, consequence="Borrar borradores.")):
            with self.subTest(request=request):
                with self.assertRaises(AssertionError):
                    self.check(request)

    def test_accepts_every_documented_example(self):
        for doc in DOCS:
            for block in JSON_BLOCK.findall(doc.read_text(encoding="utf-8")):
                self.check(json.loads(block))


if __name__ == "__main__":
    unittest.main()
