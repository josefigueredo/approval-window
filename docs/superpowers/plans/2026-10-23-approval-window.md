# approval-window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A global `awin` command that any skill CLI calls before a consequential action, showing a native macOS approval window built from data (not HTML), plus the `approval-window` skill that teaches agents to wire it and the `approval-demo` test skill.

**Architecture:** Python (stdlib only) validates a JSON request, renders an escaped HTML page and launches a JXA script (`osascript -l JavaScript`) that shows an `NSPanel` with a JavaScript-disabled `WKWebView` and two native buttons. The script beeps once, prints `approved` or `cancelled`; `awin` maps that to an exit code. The calling CLI performs the action; `awin` only asks.

**Tech Stack:** Python ≥ 3.9 stdlib, `unittest`; JXA with Cocoa + WebKit; bash `install.sh`.

**Spec:** `docs/superpowers/specs/2026-10-23-approval-window-design.md` (approved 2026-10-23). Approved mockups: `docs/maquetas/ventana-estilos.html`. Prior art (read, never edit): `../jira-kanban/jkan/alert.js`, `../jira-kanban/jkan/approval.py`.

## Global Constraints

- macOS only. Windows/Linux: `awin` exits 3, never pretends.
- Python must run on `/usr/bin/python3` (3.9) and 3.12; stdlib only. Suite: `python3 -m unittest discover -s tests` and `/usr/bin/python3 -m unittest discover -s tests`.
- TDD and conventional commits; no AI attribution in commits.
- Code, CLI messages and SKILL.md in English; human docs in Rioplatense Spanish following `harness-docs` (`hdoc check` must pass). Window copy is Spanish (as in jtk).
- No approval without a person's click: no `--yes`, no env var, no pre-approval file, no default button, no key equivalent on Approve. Enter never approves; Escape, close, failure and timeout all mean `cancelled`.
- The caller sends data only; every string is HTML-escaped; the web view has JavaScript disabled.
- Approve is disabled until the page finished loading.
- One `NSBeep` when the window appears, for every level.
- Do not touch `jira-kanban`, `confluence-team-kit`, `product-brain-mcp` or any published skill.
- Harnesses in scope: Cursor agent and GitHub Copilot CLI (terminal). Claude Code works too, but is not a gate.

## Protocol (fixed here; every task uses it)

Request JSON (stdin, or `--spec FILE`). Unknown keys are rejected.

| Key | Type | Required | Limit / values |
|---|---|---|---|
| `skill` | str | yes | 1–40 chars; shown in the title bar |
| `consequence` | str | yes | 1–140 chars; the heading |
| `reversibility` | str | yes | `irreversible`, `partial`, `reversible_manual`, `reversible_planned` |
| `audience` | str | yes | `me`, `team`, `external` |
| `risk_note` | str | no | ≤ 140; default per level below |
| `undo` | str | required for `reversible_planned` | ≤ 200; shown as a row |
| `summary` | list of `[label, value]` | no | ≤ 6 rows; label ≤ 30, value ≤ 100 |
| `detail` | list of str | no | lines ≤ 300 chars; past 200 lines, truncated with «… y N más» |
| `approve_label` | str | no | 1–24 chars; default `Apruebo` |
| `style` | str | no | `alert` (default), `edge`, `tag` |

Default `risk_note`: `irreversible` «No se puede deshacer.» · `partial` «Se puede revertir, pero deja rastro.» · `reversible_manual` «Se puede deshacer, pero a mano.» · `reversible_planned` «Se puede deshacer con un comando.»
Audience row label «Lo ve»: `me` «Solo vos» · `team` «Tu equipo» · `external` «Gente de afuera».
Level colors: `irreversible` `#ff3b30` · `partial` `#ff9f0a` · `reversible_manual` `#ffcc00` · `reversible_planned` `#0a84ff`.
`reversible_planned` without `undo`: downgrade to `reversible_manual`, print `awin: reversible_planned without undo; shown as reversible_manual` to stderr, continue.

Output: one word on stdout (`approved` / `cancelled`) only for exit 0/1. Exit codes: `0` approved · `1` cancelled, closed, timed out · `2` invalid input (window never opens; message on stderr) · `3` no window available (not macOS, no `/usr/bin/osascript`, or osascript failed).
Options: `awin [--spec FILE] [--timeout SECONDS]`, `awin --version`. `--timeout` may lower, never raise, `MAX_TIMEOUT`.

## Review Focus

1. Caller text containing `<script>`, `&`, quotes, emoji or a 500-char word with no spaces → shown literally, escaped, wrapped (`overflow-wrap:anywhere`), never executed or breaking layout. Test in Task 2.
2. A request with an extra key such as `"approved": true` or `"yes": true` → exit 2 and no window. Test in Task 1.
3. Empty stdin, invalid JSON, a JSON array instead of an object, non-UTF-8 bytes → exit 2 with a one-line reason. Test in Task 4.
4. osascript hangs past the timeout or is killed → exit 1 (`cancelled`), never 0. Test in Task 3.
5. A 10 000-line `detail` → truncated to 200 lines with «… y 9800 más»; window height capped. Test in Task 2.

---

### Task 0: Measure Copilot CLI (gate)

**Files:**
- Create: `docs/mediciones.md`

**Interfaces:**
- Produces: `MAX_TIMEOUT` value (seconds) and the Copilot CLI skills folder, recorded in `docs/mediciones.md`; Task 3 and Task 6 read them.

- [ ] **Step 1:** Record `copilot --version` and the date.
- [ ] **Step 2:** Find where Copilot CLI loads skills (its docs via context7 or `copilot --help`, then confirm by installing a one-line throwaway skill and asking Copilot CLI to list skills). Record the folder.
- [ ] **Step 3:** Measure the tool-call cut: ask Copilot CLI to run `sleep 30`, `sleep 90`, `sleep 150` (separately) and record whether each completed or was cut, and after how long.
- [ ] **Step 4:** Rule: `MAX_TIMEOUT = min(120, copilot_cut) - 20` seconds. **If `copilot_cut` < 60 s, stop and report to the user before continuing** (spec decision).
- [ ] **Step 5:** Commit: `docs: measure Copilot CLI tool timeout and skills folder`

### Task 1: Request model and validation

**Files:**
- Create: `awin/__init__.py` (`__version__ = "0.1.0"`), `awin/request.py`
- Test: `tests/test_request.py`

**Interfaces:**
- Produces: `parse(data: object) -> Request`; `class InvalidRequest(ValueError)`; frozen dataclass `Request(skill, consequence, reversibility, audience, risk_note, undo, summary: tuple[tuple[str,str],...], detail: tuple[str,...], hidden_lines: int, approve_label, style, warnings: tuple[str,...])` with `risk_note` already defaulted, `reversibility` already downgraded, `detail` already truncated. Constants `LEVELS`, `AUDIENCES`, `STYLES`, `DEFAULT_RISK_NOTE: dict`, `AUDIENCE_LABEL: dict`, `MAX_DETAIL_LINES = 200`.

- [ ] **Step 1: Write the failing tests**

```python
def test_minimal_request_gets_defaults(self):
    r = parse({"skill": "demo", "consequence": "Vas a borrar 3 notas", "reversibility": "irreversible", "audience": "me"})
    self.assertEqual((r.style, r.approve_label, r.risk_note), ("alert", "Apruebo", "No se puede deshacer."))
def test_unknown_key_is_rejected(self):          # Review Focus 2
    for extra in ({"approved": True}, {"yes": True}):
        with self.assertRaises(InvalidRequest): parse({**MIN, **extra})
def test_missing_required_key_is_rejected(self): # each of skill, consequence, reversibility, audience
def test_bad_enum_is_rejected(self):             # reversibility="maybe", audience="all", style="red"
def test_limits_are_enforced(self):              # consequence 141 chars, 7 summary rows, label 31, approve_label 25
def test_planned_without_undo_downgrades(self):
    r = parse({**MIN, "reversibility": "reversible_planned"})
    self.assertEqual(r.reversibility, "reversible_manual"); self.assertTrue(r.warnings)
def test_planned_with_undo_keeps_level(self):
def test_detail_is_truncated(self):              # Review Focus 5
    r = parse({**MIN, "detail": ["x"] * 10000})
    self.assertEqual((len(r.detail), r.hidden_lines), (200, 9800))
def test_non_object_is_rejected(self):           # [], "x", None
```

- [ ] **Step 2:** Run `python3 -m unittest tests.test_request -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `parse` in `awin/request.py`; error messages name the key (`"unknown key: approved"`).
- [ ] **Step 4:** Run with `python3` and `/usr/bin/python3` → PASS.
- [ ] **Step 5:** Commit `feat: validate approval requests`

### Task 2: Render the page

**Files:**
- Create: `awin/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Request` (Task 1).
- Produces: `render_html(req: Request) -> str`; `window_height(req: Request) -> int` (page area, capped at `MAX_HEIGHT = 560`); `LEVEL_COLOR: dict`.

Layout follows `docs/maquetas/ventana-estilos.html`: `alert` = colored icon left + risk line under heading; `edge` = 4 px color strip; `tag` = pill above heading and tinted Approve border (the tint goes to the JXA button in Task 3, not the page). Rows in order: summary rows, then «Lo ve», then «Para deshacer» (only with `undo`). Detail in `<details><summary>Mostrar detalle (N)</summary>…` (works with JS off). Light/dark via `prefers-color-scheme`. `overflow-wrap:anywhere` on all text. No `<script>`, no external URL.

- [ ] **Step 1: Write the failing tests**

```python
def test_text_is_escaped(self):                  # Review Focus 1
    html = render_html(parse({**MIN, "consequence": "<script>alert(1)</script> & \"x\""}))
    self.assertNotIn("<script>", html); self.assertIn("&lt;script&gt;", html)
def test_long_word_wraps(self):                  # 500-char word → css has overflow-wrap:anywhere
def test_each_level_uses_its_color(self):        # 4 levels → LEVEL_COLOR value appears
def test_each_style_has_its_marker(self):        # class "style-alert" / "style-edge" / "style-tag" on body
def test_audience_and_undo_rows(self):           # "Lo ve" + "Tu equipo"; "Para deshacer" only with undo
def test_truncated_detail_says_how_many(self):   # "… y 9800 más"
def test_page_has_no_script_or_remote_url(self): # no "<script", no "http://", no "https://" outside caller text
def test_height_is_capped(self):                 # 10000-line detail → window_height == 560
def test_dark_mode_rules_exist(self):            # "prefers-color-scheme: dark" in html
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with `html.escape` on every caller string; CSS inline in a constant.
- [ ] **Step 4:** Run both Pythons → PASS.
- [ ] **Step 5:** Commit `feat: render the approval page from a request`

### Task 3: The native window

**Files:**
- Create: `awin/window.js`, `awin/window.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `render_html`, `window_height`, `LEVEL_COLOR` (Task 2); `MAX_TIMEOUT` from `docs/mediciones.md` (Task 0).
- Produces: `class Unavailable(Exception)`; `available(platform=None, osascript=OSASCRIPT) -> bool`; `ask(req: Request, timeout: int, runner=None) -> bool` (True only when the script printed exactly `approved`); constants `OSASCRIPT = "/usr/bin/osascript"`, `MAX_TIMEOUT`, `DEFAULT_TIMEOUT = MAX_TIMEOUT`.

`window.js` argv: `<html file> <title> <approve label> <page height> <tag tint hex or "">`. Behavior copied from the prior art `../jira-kanban/jkan/alert.js` (read it): `NSPanel` floating, JS-disabled `WKWebView`, Approve with `keyEquivalent = ''` and `enabled = false` until `didFinishNavigation`, one reload on failure, Cancelar with Escape, close = cancel, https links open in the browser. **New:** call `$.NSBeep()` once right after `makeKeyAndOrderFront`; when the tint arg is set, give Approve a colored border without making it default. Title bar: `<skill> · Aprobación`.

`ask` writes the page to a temp file (deleted afterwards), runs `[OSASCRIPT, "-l", "JavaScript", window.js, path, title, label, height, tint]` with `subprocess.run(..., timeout=timeout)`.

- [ ] **Step 1: Write the failing tests** (runner injected; no real window)

```python
def test_approved_only_on_exact_word(self):      # stdout "approved\n" → True; "approved!" / "" → False
def test_cancelled_is_false(self):
def test_timeout_is_cancel(self):                # Review Focus 4: runner raises subprocess.TimeoutExpired → False
def test_osascript_failure_is_unavailable(self): # returncode 1 → raises Unavailable
def test_not_macos_is_unavailable(self):         # available(platform="linux") is False
def test_argv_shape(self):                       # osascript -l JavaScript window.js <file> "<skill> · Aprobación" ...
def test_tint_only_for_tag_style(self):          # tag → LEVEL_COLOR hex; alert/edge → ""
def test_temp_page_is_removed(self):
def test_script_has_no_approve_shortcut(self):   # window.js source: approve keyEquivalent '' , enabled = false, contains NSBeep
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `window.py` and `window.js`.
- [ ] **Step 4:** Run both Pythons → PASS.
- [ ] **Step 5: Manual check (person present).** `python3 -c` a call to `ask` for each of the 4 levels × 3 styles (a helper `tools/preview.py` that loops them is fine). Check and record in `docs/mediciones.md`: beep sounds once; Enter does nothing; Escape → cancelled; red close → cancelled; leaving it → cancelled at the timeout; Approve gray until content shows; light and dark mode both readable. The agent launches it and asks the person to click; the agent never clicks.
- [ ] **Step 6:** Commit `feat: native approval window with beep and no default button`

### Task 4: The `awin` command

**Files:**
- Create: `awin.py` (entry, `#!/usr/bin/env python3`, calls `awin.cli.main`), `awin/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `parse`, `InvalidRequest` (Task 1); `ask`, `available`, `Unavailable`, `MAX_TIMEOUT`, `DEFAULT_TIMEOUT` (Task 3).
- Produces: `main(argv: list[str], stdin=sys.stdin.buffer, stdout=sys.stdout, stderr=sys.stderr, asker=None, is_available=None) -> int`.

- [ ] **Step 1: Write the failing tests**

```python
def test_approved_exit_0_and_word(self):         # asker returns True → 0, stdout "approved\n"
def test_cancelled_exit_1(self):
def test_invalid_input_exit_2_no_window(self):   # Review Focus 3: b"", b"{", b"[]", b"\xff" → 2, asker never called
def test_unavailable_exit_3(self):               # is_available False → 3; asker raises Unavailable → 3; stdout empty
def test_spec_file_option(self):
def test_timeout_can_only_lower(self):           # --timeout 30 → asker gets 30; --timeout 9999 → exit 2
def test_no_approval_shortcut_exists(self):      # parser has no option besides --spec, --timeout, --version, -h
def test_warnings_go_to_stderr(self):            # planned without undo → stderr line, still asks
def test_version(self):
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with `argparse`; read bytes, decode UTF-8 strictly.
- [ ] **Step 4:** Run both Pythons → PASS.
- [ ] **Step 5:** Commit `feat: awin command with exit codes`

### Task 5: Install and docs

**Files:**
- Create: `install.sh`, `README.md`, `docs/instalacion.md`, `docs/referencia.md`, `docs/showcase.md`, `.gitignore`
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: Copilot CLI skills folder (Task 0).
- Produces: `~/.local/bin/awin` → `awin.py`; skills `approval-window` and `approval-demo` linked in `~/.agents/skills/<name>` and from `~/.claude/skills`, `~/.cursor/skills`, `~/.codex/skills` and the Copilot CLI folder. Same `link()` rule as `../jira-kanban/install.sh` (never replace a real file; exit 1).

- [ ] **Step 1:** Failing test: run `install.sh` with `HOME` pointed at a temp dir; assert each link exists and points into the repo; a real file at a link path → exit 1 and file untouched; re-running is safe.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Write the docs per `harness-docs` (load that skill): README index, install with prompts, reference = the Protocol table above, showcase with real captures of the window from Task 3 (labelled as real output). Run `python3 ~/.agents/skills/harness-docs/hdoc.py check .` → no errors.
- [ ] **Step 6:** Commit `feat: install script and docs`

### Task 6: The `approval-demo` test skill

**Files:**
- Create: `approval-demo/SKILL.md`, `approval-demo/demo.py`
- Test: `tests/test_demo.py`

**Interfaces:**
- Consumes: the `awin` command and its exit codes (Task 4).
- Produces: `demo.py <action>` with actions `delete-note` (irreversible, style alert), `share-note` (partial, external, style tag), `rename-notes` (reversible_manual, edge), `archive-notes` (reversible_planned with `undo: "demo.py unarchive-notes"`, alert) plus `unarchive-notes`. Data in `~/.local/state/approval-demo/notes.json` (created with 3 sample notes). Each action builds its request, calls `awin` via `subprocess.run(["awin"], input=json)` resolved with `shutil.which`, writes only on exit 0, prints `not done: cancelled` on 1, refuses with exit 3 and a clear message when `awin` is missing or returns 3.

- [ ] **Step 1:** Failing tests with the `awin` call injected (`run_awin` parameter): approved → file changed; cancelled → file unchanged; missing awin → exit 3, file unchanged; each action's request passes `awin.request.parse` and has the level/style above.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS on both Pythons.
- [ ] **Step 5:** SKILL.md (English): when the user asks to try the approval window, run one `demo.py` action, tell them a window will appear first, report the result word.
- [ ] **Step 6:** Commit `feat: approval-demo test skill`

### Task 7: The `approval-window` skill and its evaluation

**Files:**
- Create: `SKILL.md` (repo root = skill `approval-window`), `references/protocol.md`, `references/choosing-a-level.md`, `examples/notes-cli/notes.py`, `examples/notes-cli/tests/test_notes.py`, `docs/evaluacion-skill.md`

**Interfaces:**
- Consumes: Protocol (above), `approval-demo` as the worked example.
- Produces: a skill whose steps are: (1) list the CLI's actions with effects outside the process; (2) pick the level by the questions «¿hay comando para deshacer? ¿queda rastro? ¿se puede deshacer?» in `choosing-a-level.md`, with the examples from the spec table; (3) write `consequence` as «Vas a <verbo> <cantidad> <qué> en <dónde>»; (4) call `awin` before the write, act only on exit 0, refuse on 3; (5) test by injecting the call (pattern of `approval-demo/demo.py`), never by a bypass flag. Must state: never add a `--yes`, never pass `reversible_planned` without a real undo command.
- `examples/notes-cli/notes.py`: a tiny CLI with `add` and `clear` (deletes all notes) and passing tests, **without** the window: the evaluation fixture.

- [ ] **Step 1:** Write `examples/notes-cli` with its tests passing (`python3 -m unittest discover -s examples/notes-cli/tests`).
- [ ] **Step 2:** Write `SKILL.md` and the two references.
- [ ] **Step 3: Evaluate (spec criterion 4).** Copy `examples/notes-cli` to a temp dir; dispatch a fresh Claude Code subagent that loads only this skill and is told «add an approval window to this CLI». Pass when: `clear` calls `awin` with `irreversible`, `add` does not, its new tests pass, no bypass flag exists. Record the run and diff in `docs/evaluacion-skill.md`; the user reviews the diff.
- [ ] **Step 4:** Commit `feat: approval-window skill with evaluation`

### Task 8: End-to-end in Cursor and Copilot CLI

**Files:**
- Modify: `docs/mediciones.md`

- [ ] **Step 1:** Run `./install.sh`; confirm `awin --version` and that Cursor and Copilot CLI list `approval-demo`.
- [ ] **Step 2:** In Cursor's agent (via `run-in-cursor` or by the user), ask it to try `approval-demo` `delete-note`; the user approves → note gone. Repeat with `archive-notes`; the user cancels → nothing changes.
- [ ] **Step 3:** Same two runs in Copilot CLI.
- [ ] **Step 4:** Record harness versions, actions, results and screenshots in `docs/mediciones.md`.
- [ ] **Step 5:** Commit `docs: record end-to-end runs in Cursor and Copilot CLI`
