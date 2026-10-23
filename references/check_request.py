"""Stdlib check of an awin request, to copy into a CLI's tests (Python 3.9+).

Mirrors the protocol in references/protocol.md and adds two rules awin itself does not enforce:
the consequence starts with "Vas a " and `reversible_planned` carries `undo`.
Raises AssertionError naming the first problem. Text must not hold control characters (newlines and tabs too),
lone surrogates or bidi override characters, and required text must not be only whitespace.

When the approval-window repo is importable, also run its real parser:
    from awin.request import parse; assert parse(request).warnings == ()
"""
import re

REQUIRED = ("skill", "consequence", "reversibility", "audience")
OPTIONAL = ("risk_note", "undo", "summary", "detail", "approve_label", "style")
LEVELS = ("irreversible", "partial", "reversible_manual", "reversible_planned")
AUDIENCES = ("me", "team", "external")
STYLES = ("alert", "edge", "tag")
# C0 controls, DEL, lone surrogates and bidi overrides/isolates: awin rejects them in every string.
FORBIDDEN = re.compile("[\x00-\x1f\x7f\ud800-\udfff\u202a-\u202e\u2066-\u2069]")


def _clean(key, value):
    assert not FORBIDDEN.search(value), "%s contains a control, surrogate or bidi override character" % key


def _text(request, key, low, high):
    value = request[key]
    assert isinstance(value, str), "%s must be a string" % key
    assert low <= len(value) <= high, "%s must be %d-%d characters, got %d" % (key, low, high, len(value))
    _clean(key, value)
    if low:
        assert value.strip(), "%s must not be only whitespace" % key


def check_request(request):
    assert isinstance(request, dict), "request must be a dict"
    unknown = set(request) - set(REQUIRED) - set(OPTIONAL)
    assert not unknown, "unknown keys: %s" % ", ".join(sorted(unknown))
    for key in REQUIRED:
        assert key in request, "missing required key: %s" % key

    _text(request, "skill", 1, 40)
    _text(request, "consequence", 1, 140)
    assert request["consequence"].startswith("Vas a "), "consequence must start with 'Vas a '"
    assert request["reversibility"] in LEVELS, "reversibility must be one of %s" % (LEVELS,)
    assert request["audience"] in AUDIENCES, "audience must be one of %s" % (AUDIENCES,)
    if "style" in request:
        assert request["style"] in STYLES, "style must be one of %s" % (STYLES,)
    if request["reversibility"] == "reversible_planned":
        assert request.get("undo"), "reversible_planned needs undo"
    if "undo" in request:
        _text(request, "undo", 0, 200)
    if "risk_note" in request:
        _text(request, "risk_note", 0, 140)
    if "approve_label" in request:
        _text(request, "approve_label", 1, 24)

    summary = request.get("summary", [])
    assert isinstance(summary, list) and len(summary) <= 6, "summary must be a list of at most 6 rows"
    for row in summary:
        assert isinstance(row, (list, tuple)) and len(row) == 2, "summary rows must be [label, value]"
        label, value = row
        assert isinstance(label, str) and 1 <= len(label) <= 30, "summary label must be 1-30 characters"
        assert isinstance(value, str) and len(value) <= 100, "summary value must be at most 100 characters"
        _clean("summary label", label)
        _clean("summary value", value)

    detail = request.get("detail", [])
    assert isinstance(detail, list), "detail must be a list"
    for line in detail:
        assert isinstance(line, str) and len(line) <= 300, "detail lines must be strings of at most 300 characters"
        _clean("detail line", line)
