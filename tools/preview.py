"""Open one real approval window per level x style and print each result.

Manual check only (needs a person to click). Run from the repo root:
    python3 tools/preview.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from awin.request import LEVELS, STYLES, parse  # noqa: E402
from awin.window import DEFAULT_TIMEOUT, Unavailable, ask  # noqa: E402


def main() -> int:
    for level in LEVELS:
        for style in STYLES:
            req = parse({
                "skill": "preview",
                "consequence": f"{level} / {style}",
                "reversibility": level,
                "audience": "team",
                "undo": "preview undo",
                "summary": [["Nivel", level], ["Estilo", style]],
                "detail": [f"line {n}" for n in range(1, 8)],
                "style": style,
            })
            try:
                outcome = "approved" if ask(req, DEFAULT_TIMEOUT) else "cancelled"
            except Unavailable as exc:
                outcome = f"unavailable ({exc})"
            print(f"{level:20} {style:6} -> {outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
