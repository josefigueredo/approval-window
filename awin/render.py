"""Render the approval page for awin. Stdlib only, Python 3.9 compatible.

The page is shown in a WKWebView with JavaScript disabled, so it carries no
script and no external resource. Every caller string goes through html.escape.
"""
from __future__ import annotations

import math
from html import escape

from awin.request import AUDIENCE_LABEL, Request

MAX_HEIGHT = 560
MIN_HEIGHT = 200

LEVEL_COLOR = {
    "irreversible": "#ff3b30",
    "partial": "#ff9f0a",
    "reversible_manual": "#ffcc00",
    "reversible_planned": "#0a84ff",
}

_ICON = {
    "irreversible": "!",
    "partial": "!",
    "reversible_manual": "!",
    "reversible_planned": "i",
}

_CSS = """
:root{color-scheme:light dark;--fg:#1d1d1f;--muted:#6e6e73;--bg:#f6f6f8;--panel:rgba(0,0,0,.04);--line:rgba(0,0,0,.08);--link:#0066d6}
@media (prefers-color-scheme: dark){:root{--fg:#f5f5f7;--muted:#a1a1a6;--bg:#2a2a2c;--panel:rgba(255,255,255,.07);--line:rgba(255,255,255,.12);--link:#4da3ff}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg)}
body{font:13px -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif;color:var(--fg);padding:20px 20px 14px;overflow-wrap:anywhere;word-break:normal}
.layout{display:flex;gap:12px}
.body{flex:1;min-width:0}
.h{font-size:15px;font-weight:700;margin:2px 0 4px;letter-spacing:-.01em;overflow-wrap:anywhere}
.risk{color:var(--muted);font-size:12px;line-height:1.4;overflow-wrap:anywhere}
.icon{width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;flex:none;background:__COLOR__;color:#fff}
.strip{width:4px;background:__COLOR__;border-radius:0 2px 2px 0;margin:6px 0;flex:none}
.style-edge .layout{gap:16px}
.style-edge{padding-left:0}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;background:__TINT__;color:var(--fg);max-width:100%;overflow-wrap:anywhere}
.dot{width:7px;height:7px;border-radius:50%;background:__COLOR__;flex:none}
.style-tag .h{margin-top:8px}
.kv{margin-top:10px;border-radius:8px;background:var(--panel)}
.row{display:flex;justify-content:space-between;gap:12px;padding:6px 10px;font-size:12px}
.row+.row{border-top:.5px solid var(--line)}
.row span{color:var(--muted);flex:none;max-width:45%;overflow-wrap:anywhere}
.row b{font-weight:600;text-align:right;min-width:0;overflow-wrap:anywhere}
details{margin-top:8px;font-size:12px}
summary{color:var(--link);cursor:default}
pre{margin:6px 0 0;padding:8px 10px;border-radius:8px;background:var(--panel);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.more{color:var(--muted)}
"""


def _tint(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "rgba(%d,%d,%d,.2)" % (r, g, b)


def _css(color: str) -> str:
    return (_CSS.replace("__COLOR__", color).replace("__TINT__", _tint(color))).strip()


def _row(label: str, value: str) -> str:
    return "<div class=\"row\"><span>%s</span><b>%s</b></div>" % (escape(label), escape(value))


def render_html(req: Request) -> str:
    color = LEVEL_COLOR[req.reversibility]
    heading = "<div class=\"h\">%s</div>" % escape(req.consequence)
    risk = "<div class=\"risk\">%s</div>" % escape(req.risk_note)

    rows = [_row(label, value) for label, value in req.summary]
    rows.append(_row("Lo ve", AUDIENCE_LABEL[req.audience]))
    if req.undo:
        rows.append(_row("Para deshacer", req.undo))
    kv = "<div class=\"kv\">%s</div>" % "".join(rows)

    detail = ""
    if req.detail:
        text = "\n".join(escape(line) for line in req.detail)
        if req.hidden_lines > 0:
            text += "\n<span class=\"more\">… y %d más</span>" % req.hidden_lines
        detail = "<details><summary>Mostrar detalle (%d)</summary><pre>%s</pre></details>" % (
            len(req.detail), text)

    if req.style == "tag":
        pill = "<span class=\"pill\"><span class=\"dot\"></span>%s</span>" % escape(req.risk_note)
        content = "<div class=\"body\">%s%s%s%s</div>" % (pill, heading, kv, detail)
    else:
        inner = "<div class=\"body\">%s%s%s%s</div>" % (heading, risk, kv, detail)
        lead = ("<div class=\"icon\">%s</div>" % _ICON[req.reversibility]
                if req.style == "alert" else "<div class=\"strip\"></div>")
        content = lead + inner

    return (
        "<!doctype html>\n<html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<style>%s</style></head><body class=\"style-%s\"><div class=\"layout\">%s</div></body></html>\n"
        % (_css(color), req.style, content)
    )


def _lines(text: str, per_line: int) -> int:
    return max(1, math.ceil(len(text) / per_line))


def window_height(req: Request) -> int:
    """Page-area height in px; an estimate that errs tall, for the collapsed page, capped at MAX_HEIGHT."""
    h = 56 + 20 * _lines(req.consequence, 38) + 17 * _lines(req.risk_note, 55)
    h += 10
    for label, value in req.summary:
        h += 14 + 16 * max(_lines(label, 20), _lines(value, 30))
    h += 30  # audience row
    if req.undo:
        h += 14 + 16 * _lines(req.undo, 30)
    if req.detail:
        h += 30  # the collapsed «Mostrar detalle» line only; expanding it scrolls the web view
    return min(MAX_HEIGHT, max(MIN_HEIGHT, int(h)))
