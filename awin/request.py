"""Request model and validation for awin. Stdlib only, Python 3.9 compatible."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

LEVELS = ("irreversible", "partial", "reversible_manual", "reversible_planned")
AUDIENCES = ("me", "team", "external")
STYLES = ("alert", "edge", "tag")
DEFAULT_RISK_NOTE = {
    "irreversible": "No se puede deshacer.",
    "partial": "Se puede revertir, pero deja rastro.",
    "reversible_manual": "Se puede deshacer, pero a mano.",
    "reversible_planned": "Se puede deshacer con un comando.",
}
AUDIENCE_LABEL = {
    "me": "Solo vos",
    "team": "Tu equipo",
    "external": "Gente de afuera",
}
MAX_DETAIL_LINES = 200

_KEYS = frozenset((
    "skill", "consequence", "reversibility", "audience", "risk_note", "undo",
    "summary", "detail", "approve_label", "style",
))
# C0 controls and DEL (a NUL cannot cross argv; a newline would fake a line), lone surrogates (cannot be written as
# UTF-8) and bidi overrides/isolates (they reorder what the person reads).
_FORBIDDEN = re.compile("[\x00-\x1f\x7f\ud800-\udfff\u202a-\u202e\u2066-\u2069]")
_DOWNGRADE_WARNING = "reversible_planned without undo; shown as reversible_manual"


class InvalidRequest(ValueError):
    """The request failed validation; the message names the offending key."""


@dataclass(frozen=True)
class Request:
    skill: str
    consequence: str
    reversibility: str
    audience: str
    risk_note: str
    undo: Optional[str]
    summary: Tuple[Tuple[str, str], ...]
    detail: Tuple[str, ...]
    hidden_lines: int
    approve_label: str
    style: str
    warnings: Tuple[str, ...]


def _clean(key, value):
    """Reject characters that break argv or the page, or that change what the person reads."""
    if _FORBIDDEN.search(value):
        raise InvalidRequest("%s contains a control, surrogate or bidi override character" % key)
    return value


def _text(data, key, max_len, min_len=0):
    value = data[key]
    if not isinstance(value, str):
        raise InvalidRequest("%s must be a string" % key)
    if len(value) < min_len or len(value) > max_len:
        raise InvalidRequest("%s must be %d-%d characters" % (key, min_len, max_len))
    _clean(key, value)
    if min_len and not value.strip():
        raise InvalidRequest("%s must not be only whitespace" % key)
    return value


def _choice(data, key, allowed):
    value = data[key]
    if not isinstance(value, str) or value not in allowed:
        raise InvalidRequest("%s must be one of: %s" % (key, ", ".join(allowed)))
    return value


def _list(data, key):
    value = data[key]
    if not isinstance(value, (list, tuple)):
        raise InvalidRequest("%s must be a list" % key)
    return value


def parse(data: object) -> Request:
    if not isinstance(data, dict):
        raise InvalidRequest("request must be a JSON object")
    for key in data:
        if key not in _KEYS:
            raise InvalidRequest("unknown key: %s" % key)
    for key in ("skill", "consequence", "reversibility", "audience"):
        if key not in data:
            raise InvalidRequest("missing required key: %s" % key)

    skill = _text(data, "skill", 40, 1)
    consequence = _text(data, "consequence", 140, 1)
    reversibility = _choice(data, "reversibility", LEVELS)
    audience = _choice(data, "audience", AUDIENCES)

    undo = _text(data, "undo", 200) if "undo" in data else None
    warnings = []
    if reversibility == "reversible_planned" and not undo:
        reversibility = "reversible_manual"
        warnings.append(_DOWNGRADE_WARNING)
        print("awin: " + _DOWNGRADE_WARNING, file=sys.stderr)

    risk_note = _text(data, "risk_note", 140) if "risk_note" in data else ""
    if not risk_note:
        risk_note = DEFAULT_RISK_NOTE[reversibility]

    summary = []
    if "summary" in data:
        rows = _list(data, "summary")
        if len(rows) > 6:
            raise InvalidRequest("summary must have at most 6 rows")
        for row in rows:
            if (not isinstance(row, (list, tuple)) or len(row) != 2
                    or not all(isinstance(x, str) for x in row)):
                raise InvalidRequest("summary rows must be [label, value] strings")
            label, value = row
            _clean("summary label", label)
            _clean("summary value", value)
            if not 1 <= len(label) <= 30:
                raise InvalidRequest("summary label must be 1-30 characters")
            if len(value) > 100:
                raise InvalidRequest("summary value must be at most 100 characters")
            summary.append((label, value))

    detail = ()
    hidden = 0
    if "detail" in data:
        lines = _list(data, "detail")
        for line in lines:
            if not isinstance(line, str):
                raise InvalidRequest("detail lines must be strings")
            if len(line) > 300:
                raise InvalidRequest("detail lines must be at most 300 characters")
            _clean("detail line", line)
        detail = tuple(lines[:MAX_DETAIL_LINES])
        hidden = len(lines) - len(detail)

    approve_label = _text(data, "approve_label", 24, 1) if "approve_label" in data else "Apruebo"
    style = _choice(data, "style", STYLES) if "style" in data else "alert"

    return Request(
        skill=skill, consequence=consequence, reversibility=reversibility,
        audience=audience, risk_note=risk_note, undo=undo or None,
        summary=tuple(summary), detail=detail, hidden_lines=hidden,
        approve_label=approve_label, style=style, warnings=tuple(warnings),
    )
