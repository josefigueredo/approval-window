"""Checks on the approval-window skill: frontmatter, links, and that every example request is valid."""
import contextlib
import io
import json
import re
import unittest
from pathlib import Path

from awin.request import parse

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
DOCS = (SKILL, ROOT / "references" / "protocol.md", ROOT / "references" / "choosing-a-level.md")
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


if __name__ == "__main__":
    unittest.main()
