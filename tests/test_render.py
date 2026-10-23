import contextlib
import io
import re
import unittest

from awin.render import LEVEL_COLOR, MAX_HEIGHT, render_html, window_height
from awin.request import LEVELS, STYLES, parse

MIN = {
    "skill": "demo",
    "consequence": "Vas a borrar 3 notas",
    "reversibility": "irreversible",
    "audience": "me",
}


def build(**extra):
    with contextlib.redirect_stderr(io.StringIO()):
        return parse({**MIN, **extra})


class RenderTests(unittest.TestCase):
    def test_is_complete_utf8_document(self):
        html = render_html(build())
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', html.lower())
        self.assertIn("</html>", html)

    def test_text_is_escaped(self):
        html = render_html(build(consequence='<script>alert(1)</script> & "x"',
                                 summary=[["<b>l</b>", "<i>v</i>"]],
                                 detail=["<img src=x onerror=1>"],
                                 undo="<u>cmd</u>", risk_note="<em>r</em>"))
        self.assertNotIn("<script", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;x&quot;", html)
        for raw in ("<b>l</b>", "<i>v</i>", "<img", "<u>cmd", "<em>r"):
            self.assertNotIn(raw, html)

    def test_emoji_and_long_word_kept(self):
        word = "A" * 300
        html = render_html(build(consequence="Borrar \U0001F525", detail=[word]))
        self.assertIn("\U0001F525", html)
        self.assertIn(word, html)
        self.assertIn("overflow-wrap:anywhere", html)

    def test_each_level_uses_its_color(self):
        self.assertEqual(set(LEVEL_COLOR), set(LEVELS))
        self.assertEqual(LEVEL_COLOR["irreversible"], "#ff3b30")
        self.assertEqual(LEVEL_COLOR["partial"], "#ff9f0a")
        self.assertEqual(LEVEL_COLOR["reversible_manual"], "#ffcc00")
        self.assertEqual(LEVEL_COLOR["reversible_planned"], "#0a84ff")
        for level in LEVELS:
            extra = {"undo": "x"} if level == "reversible_planned" else {}
            html = render_html(build(reversibility=level, **extra))
            self.assertIn(LEVEL_COLOR[level], html)
            others = [c for l, c in LEVEL_COLOR.items() if l != level]
            for c in others:
                self.assertNotIn(c, html)

    def test_each_style_has_its_marker(self):
        for style in STYLES:
            html = render_html(build(style=style))
            self.assertRegex(html, r'<body class="[^"]*\bstyle-%s\b' % style)
            for other in STYLES:
                if other != style:
                    self.assertNotIn("style-" + other + '"', html.split("<body")[1].split(">")[0])

    def test_style_structures(self):
        self.assertIn('class="icon"', render_html(build(style="alert")))
        self.assertIn('class="strip"', render_html(build(style="edge")))
        self.assertIn('class="pill"', render_html(build(style="tag")))
        self.assertNotIn('class="pill"', render_html(build(style="alert")))

    def test_risk_note_shown(self):
        self.assertIn("No se puede deshacer.", render_html(build()))
        self.assertIn("No se puede deshacer.", render_html(build(style="tag")))

    def test_audience_and_undo_rows(self):
        html = render_html(build(audience="team"))
        self.assertIn("Lo ve", html)
        self.assertIn("Tu equipo", html)
        self.assertNotIn("Para deshacer", html)
        self.assertIn("Gente de afuera", render_html(build(audience="external")))
        self.assertIn("Solo vos", render_html(build()))
        html = render_html(build(reversibility="reversible_planned", undo="git revert"))
        self.assertIn("Para deshacer", html)
        self.assertIn("git revert", html)
        html = render_html(build(undo="a mano"))
        self.assertIn("Para deshacer", html)

    def test_row_order(self):
        html = render_html(build(summary=[["Contenido", "1 épica"]], undo="u"))
        self.assertLess(html.index("Contenido"), html.index("Lo ve"))
        self.assertLess(html.index("Lo ve"), html.index("Para deshacer"))

    def test_detail_in_details_element(self):
        html = render_html(build(detail=["a", "b", "c"]))
        self.assertIn("<details>", html)
        self.assertIn("<summary>Mostrar detalle (3)</summary>", html)
        self.assertNotIn("<details", render_html(build()))

    def test_truncated_detail_says_how_many(self):
        html = render_html(build(detail=["l"] * 10000))
        self.assertIn("… y 9800 más", html)
        self.assertIn("Mostrar detalle (200)", html)
        self.assertNotIn("… y", render_html(build(detail=["l"] * 5)))

    def test_page_has_no_script_or_remote_url(self):
        html = render_html(build(summary=[["a", "b"]], detail=["x"], undo="u"))
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("url(", html)
        self.assertIsNone(re.search(r"<(link|img|iframe|object|embed)\b", html))

    def test_caller_url_is_escaped_text_only(self):
        html = render_html(build(consequence="ver https://x.io/?a=1&b=2"))
        self.assertIn("https://x.io/?a=1&amp;b=2", html)

    def test_dark_mode_rules_exist(self):
        self.assertIn("prefers-color-scheme: dark", render_html(build()))

    def test_skill_not_in_page(self):
        self.assertNotIn("zzskill", render_html(build(skill="zzskill")))


class HeightTests(unittest.TestCase):
    def test_minimum_is_sensible(self):
        h = window_height(build())
        self.assertIsInstance(h, int)
        self.assertGreaterEqual(h, 200)
        self.assertLess(h, MAX_HEIGHT)

    def test_height_is_capped(self):
        self.assertEqual(MAX_HEIGHT, 560)
        self.assertEqual(window_height(build(detail=["l"] * 10000)), 560)

    def test_grows_with_content(self):
        small = window_height(build())
        rows = window_height(build(summary=[["a", "b"]] * 6, undo="u"))
        self.assertGreater(rows, small)
        self.assertGreaterEqual(window_height(build(detail=["x"])), small)


if __name__ == "__main__":
    unittest.main()
