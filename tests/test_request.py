import contextlib
import io
import unittest

from awin.request import (
    AUDIENCE_LABEL, AUDIENCES, DEFAULT_RISK_NOTE, LEVELS, MAX_DETAIL_LINES,
    STYLES, InvalidRequest, Request, parse,
)

MIN = {
    "skill": "demo",
    "consequence": "Vas a borrar 3 notas",
    "reversibility": "irreversible",
    "audience": "me",
}


class ParseTests(unittest.TestCase):
    def test_minimal_request_gets_defaults(self):
        r = parse(dict(MIN))
        self.assertIsInstance(r, Request)
        self.assertEqual((r.style, r.approve_label, r.risk_note),
                         ("alert", "Apruebo", "No se puede deshacer."))
        self.assertEqual((r.summary, r.detail, r.hidden_lines, r.warnings, r.undo),
                         ((), (), 0, (), None))

    def test_default_risk_note_per_level(self):
        self.assertEqual(set(DEFAULT_RISK_NOTE), set(LEVELS))
        self.assertEqual(DEFAULT_RISK_NOTE["partial"], "Se puede revertir, pero deja rastro.")
        self.assertEqual(DEFAULT_RISK_NOTE["reversible_manual"], "Se puede deshacer, pero a mano.")
        self.assertEqual(DEFAULT_RISK_NOTE["reversible_planned"], "Se puede deshacer con un comando.")

    def test_constants(self):
        self.assertEqual(AUDIENCES, ("me", "team", "external"))
        self.assertEqual(STYLES, ("alert", "edge", "tag"))
        self.assertEqual(AUDIENCE_LABEL, {"me": "Solo vos", "team": "Tu equipo",
                                          "external": "Gente de afuera"})
        self.assertEqual(MAX_DETAIL_LINES, 200)

    def test_custom_values_are_kept(self):
        r = parse({**MIN, "risk_note": "ojo", "approve_label": "Borrar", "style": "tag",
                   "summary": [["Notas", "3"], ["Dónde", "Jira"]], "detail": ["a", "b"]})
        self.assertEqual((r.risk_note, r.approve_label, r.style), ("ojo", "Borrar", "tag"))
        self.assertEqual(r.summary, (("Notas", "3"), ("Dónde", "Jira")))
        self.assertEqual(r.detail, ("a", "b"))

    def test_unknown_key_is_rejected(self):
        for extra in ({"approved": True}, {"yes": True}):
            with self.assertRaises(InvalidRequest) as cm:
                parse({**MIN, **extra})
            self.assertIn("unknown key: " + next(iter(extra)), str(cm.exception))

    def test_missing_required_key_is_rejected(self):
        for key in ("skill", "consequence", "reversibility", "audience"):
            data = dict(MIN)
            del data[key]
            with self.assertRaises(InvalidRequest) as cm:
                parse(data)
            self.assertIn(key, str(cm.exception))

    def test_bad_enum_is_rejected(self):
        for key, value in (("reversibility", "maybe"), ("audience", "all"), ("style", "red")):
            with self.assertRaises(InvalidRequest) as cm:
                parse({**MIN, key: value})
            self.assertIn(key, str(cm.exception))

    def test_wrong_types_are_rejected(self):
        for key, value in (("skill", 1), ("consequence", None), ("risk_note", 5),
                           ("approve_label", True), ("undo", ["x"]),
                           ("summary", True), ("summary", 3), ("summary", "ab"),
                           ("detail", True), ("detail", 0), ("detail", "text"),
                           ("detail", [1]), ("summary", [["a"]]), ("summary", [["a", 1]]),
                           ("summary", ["ab"]), ("summary", [["", "v"]])):
            with self.assertRaises(InvalidRequest, msg=(key, value)):
                parse({**MIN, key: value})

    def test_empty_required_strings_are_rejected(self):
        for key in ("skill", "consequence", "approve_label"):
            with self.assertRaises(InvalidRequest):
                parse({**MIN, key: ""})

    def test_limits_are_enforced(self):
        bad = [
            ("skill", "x" * 41),
            ("consequence", "x" * 141),
            ("risk_note", "x" * 141),
            ("approve_label", "x" * 25),
            ("summary", [["l", "v"]] * 7),
            ("summary", [["x" * 31, "v"]]),
            ("summary", [["l", "x" * 101]]),
            ("detail", ["x" * 301]),
        ]
        for key, value in bad:
            with self.assertRaises(InvalidRequest, msg=key):
                parse({**MIN, key: value})
        with self.assertRaises(InvalidRequest):
            parse({**MIN, "reversibility": "reversible_planned", "undo": "x" * 201})

    def test_limits_accept_the_boundary(self):
        r = parse({**MIN, "skill": "x" * 40, "consequence": "x" * 140, "risk_note": "x" * 140,
                   "approve_label": "x" * 24, "summary": [["x" * 30, "y" * 100]] * 6,
                   "detail": ["z" * 300]})
        self.assertEqual(len(r.summary), 6)

    def test_length_counts_characters_not_bytes(self):
        parse({**MIN, "consequence": "ñ" * 140})
        parse({**MIN, "consequence": "\U0001F600" * 140})
        with self.assertRaises(InvalidRequest):
            parse({**MIN, "consequence": "ñ" * 141})

    def test_planned_without_undo_downgrades(self):
        with contextlib.redirect_stderr(io.StringIO()):
            r = parse({**MIN, "reversibility": "reversible_planned"})
        self.assertEqual(r.reversibility, "reversible_manual")
        self.assertEqual(r.risk_note, DEFAULT_RISK_NOTE["reversible_manual"])
        self.assertTrue(r.warnings)

    def test_downgrade_prints_stderr_line(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            parse({**MIN, "reversibility": "reversible_planned"})
        self.assertEqual(
            err.getvalue(),
            "awin: reversible_planned without undo; shown as reversible_manual\n")

    def test_planned_with_empty_undo_downgrades(self):
        with contextlib.redirect_stderr(io.StringIO()):
            r = parse({**MIN, "reversibility": "reversible_planned", "undo": ""})
        self.assertEqual(r.reversibility, "reversible_manual")

    def test_planned_with_undo_keeps_level(self):
        r = parse({**MIN, "reversibility": "reversible_planned", "undo": "git revert abc"})
        self.assertEqual((r.reversibility, r.undo, r.warnings),
                         ("reversible_planned", "git revert abc", ()))
        self.assertEqual(r.risk_note, "Se puede deshacer con un comando.")

    def test_detail_is_truncated(self):
        r = parse({**MIN, "detail": ["x"] * 10000})
        self.assertEqual((len(r.detail), r.hidden_lines), (200, 9800))

    def test_detail_at_limit_is_not_truncated(self):
        r = parse({**MIN, "detail": ["x"] * 200})
        self.assertEqual((len(r.detail), r.hidden_lines), (200, 0))

    def test_non_object_is_rejected(self):
        for data in ([], "x", None, 3, True):
            with self.assertRaises(InvalidRequest):
                parse(data)

    def test_request_is_frozen(self):
        r = parse(dict(MIN))
        with self.assertRaises(Exception):
            r.style = "tag"

    def test_invalid_request_is_value_error(self):
        self.assertTrue(issubclass(InvalidRequest, ValueError))


if __name__ == "__main__":
    unittest.main()
