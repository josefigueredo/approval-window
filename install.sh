#!/usr/bin/env bash
# Install awin (the approval window) and its skills for Claude Code, Codex, Cursor and Copilot CLI.
# CLI: ~/.local/bin/awin points at awin.py; skills call `awin`, never this folder.
# Skills: ~/.agents/skills/<name> points at this repo (approval-window) or at approval-demo/; ~/.claude/skills/<name>,
# ~/.cursor/skills/<name> and ~/.codex/skills/<name> point at ../../.agents/skills/<name>.
# Copilot CLI reads personal skills from ~/.agents/skills (measured, see docs/mediciones.md), so it needs no folder of its own.
# Re-running is safe. A real file or directory where a link goes is never replaced: the script stops with exit 1.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=("approval-window:" "approval-demo:approval-demo")  # name:folder inside the repo ("" is the repo itself)
case "${1:-}" in
  -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
  "") ;;
  *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

link() {  # link <target> <path>: create or refresh a symlink, never replace a real file or directory
  if [ -e "$2" ] && [ ! -L "$2" ]; then
    echo "refusing to replace $2: it is not a symlink; move it away and re-run" >&2
    return 1
  fi
  mkdir -p "$(dirname "$2")"
  ln -sfn "$1" "$2"
}

status=0
for entry in "${SKILLS[@]}"; do
  NAME="${entry%%:*}"
  SUB="${entry#*:}"
  TARGET="$REPO${SUB:+/$SUB}"
  link "$TARGET" "$HOME/.agents/skills/$NAME" || exit 1
  for host in .claude .codex .cursor; do
    link "../../.agents/skills/$NAME" "$HOME/$host/skills/$NAME" || status=1
  done
  echo "skill: $NAME (Claude Code, Codex, Cursor, Copilot CLI) -> $TARGET"
done
chmod +x "$REPO/awin.py"
link "$REPO/awin.py" "$HOME/.local/bin/awin" || status=1
echo "cli: awin -> $REPO/awin.py"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "note: add ~/.local/bin to PATH to use awin" >&2 ;; esac
command -v python3 >/dev/null || { echo "note: python3 is not on PATH; awin needs it" >&2; status=1; }
[ "$(uname -s)" = "Darwin" ] || echo "note: awin opens a window only on macOS; elsewhere it exits 3" >&2
exit "$status"
