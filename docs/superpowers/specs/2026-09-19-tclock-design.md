# tclock — Python/Textual port of clock-tui

Date: 2026-09-19
Status: approved for planning

## Goal

Rewrite [race604/clock-tui](https://github.com/race604/clock-tui) (Rust, ratatui) as a
Python 3.14 package named `tclock`, built with Textual, managed with uv, runnable on
Linux, macOS and Windows, and publishable to PyPI with automated versioning and release.

Feature parity with the Rust `tclock` 0.6.1 is the target. The two documented CLI
deviations are listed under "Differences from the Rust version".

## Decisions

| Topic | Decision |
|---|---|
| Distribution / import / command name | `tclock` / `tclock` / `tclock` (`pyclock` is taken on PyPI) |
| Scope | Full parity: 4 modes, all flags, config file, `--execute`, runtime mode keys, exit print, flash/blink |
| CLI framework | Typer |
| Config location | `platformdirs.user_config_path("tclock") / "config.toml"` |
| License | MIT, crediting race604/clock-tui |
| Release | GitHub Actions: CI matrix, manual bump via `uv version --bump`, trusted publishing on tag |
| Architecture | Pure-Python mode engines + one Textual rendering widget (approach A) |
| Python | `>=3.14`, `.python-version` = 3.14 |
| Build backend | `uv_build` |

## Package layout

```
tclock/
├── pyproject.toml
├── README.md
├── LICENSE
├── .python-version
├── uv.lock
├── .github/workflows/
│   ├── ci.yml
│   ├── release.yml
│   └── publish.yml
├── src/tclock/
│   ├── __init__.py       __version__ via importlib.metadata
│   ├── cli.py            Typer app → Options → resolve → run UI → post-exit print
│   ├── config.py         TOML loading, Config dataclasses
│   ├── resolve.py        Options dataclass, CLI/config/default merge, engine builders
│   ├── parsing.py        parse_duration, parse_color, parse_datetime, parse_timezone
│   ├── timefmt.py        DurationFormat, format_duration(ms, fmt)
│   ├── font.py           BricksFont glyph table, render(text, size) -> list[str]
│   ├── modes/
│   │   ├── __init__.py   re-exports
│   │   ├── base.py       Frame, Mode protocol, Pausable protocol, ElapsedClock
│   │   ├── clock.py
│   │   ├── timer.py
│   │   ├── stopwatch.py
│   │   └── countdown.py
│   ├── ui.py             ClockApp (Textual App), BigTime widget
│   └── app.tcss
└── tests/
```

Runtime dependencies: `textual>=8`, `typer`, `platformdirs`,
`tzdata; sys_platform == "win32"`.
Dev dependency group: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

## CLI

Surface mirrors the Rust tool:

```
tclock [-c/--color COLOR] [-s/--size N] [--version] [COMMAND] [COMMAND OPTIONS]

clock      -z/--timezone TZ  -D/--no-date  -S/--no-seconds  -m/--millis
timer      -d/--duration DUR (repeatable)  -t/--title T (repeatable)  -r/--repeat
           -M/--no-millis  -P/--paused  -Q/--quit  -e/--execute "shell command"
stopwatch  (no options)
countdown  -t/--time WHEN  -T/--title T  -c/--continue  -r/--reverse  -m/--millis
```

- No command → mode from `[default] mode` in config, else `clock`. Implemented with a
  Typer root callback (`invoke_without_command=True`).
- `--help` and argument errors are handled by Typer before the TUI starts. Invalid
  values exit with code 2 and a one-line message.
- Value parsers (`parsing.py`):
  - duration: `^(\d+)([smhdSMHD])$` → milliseconds.
  - color: 16 Rust names (case-insensitive) or `#rrggbb`. Name mapping to Rich:
    black, red, green, yellow, blue, magenta, cyan, white → same;
    gray → `white`, darkgray → `bright_black`, lightred → `bright_red`,
    lightgreen → `bright_green`, lightyellow → `bright_yellow`, lightblue → `bright_blue`,
    lightmagenta → `bright_magenta`, lightcyan → `bright_cyan`.
  - datetime: try in order `%H:%M`, `%H:%M:%S` (today, local), `%Y-%m-%d` (midnight,
    local), `%Y-%m-%d %H:%M:%S` (local), then `datetime.fromisoformat` (RFC 3339 with
    offset). Result is an aware datetime in local time.
  - timezone: `zoneinfo.ZoneInfo(name)`; `ZoneInfoNotFoundError` → CLI error.
- `cli.main()` is the console-script entry point. It builds an `Options` dataclass from
  parsed arguments, calls `resolve.resolve(options, config)` to obtain a mode engine plus
  display style, runs `ui.run(engine, ...)`, and after the app exits prints
  `Stopwatch time: <display_time>` to stdout if the final engine is a `Stopwatch`.

### Differences from the Rust version

1. Repeatable flags instead of variadic values: `-d 25m -d 5m -t Work -t Break`.
2. `--execute` takes a single shell string: `-e 'notify-send "Time is up"'`.

Both are documented in the README.

## Config

Path: `platformdirs.user_config_path("tclock") / "config.toml"` (honours
`$XDG_CONFIG_HOME` on Linux). Parsed with `tomllib`. Schema identical to the Rust
`examples/config.toml`:

```toml
[default]   mode = "clock"  color = "green"  size = 1
[clock]     show_date = true  show_seconds = true  show_millis = false  timezone = "..."
[timer]     durations = ["25m", "5m"]  titles = []  repeat = false  show_millis = true
            start_paused = false  auto_quit = false  execute = []
[stopwatch]
[countdown] time = "..."  title = "..."  show_millis = false  continue_on_zero = false
            reverse = false
```

`[timer] execute` (a list) is joined with spaces into the single command string.

Merge precedence: CLI flag > config file > built-in default. CLI booleans are
"set" flags, so a CLI flag can only enable a behaviour (`flag or config_value`), matching
the Rust semantics.

Failure handling:
- Missing file → defaults, silently.
- Unparseable TOML → one warning on stderr, defaults.
- Individual bad value (e.g. unknown color, bad duration) → warning naming the key, the
  built-in default for that key only.

## Mode engines (`tclock.modes`)

No Textual imports. Time is integer milliseconds from an injected `now_ms: Callable[[], int]`
(default `time.time_ns() // 1_000_000`). Wall-clock dates use an injected
`now_dt: Callable[[tzinfo | None], datetime]` (default `datetime.now`).

```python
@dataclass(frozen=True)
class Frame:
    text: str | None          # None = draw nothing this tick (blink off phase)
    header: str | None
    footer: str | None
    flash: bool = False       # timer done: green background, black digits
    finished: bool = False    # app should exit

class Mode(Protocol):
    def snapshot(self) -> Frame: ...

class Pausable(Protocol):
    def is_paused(self) -> bool: ...
    def toggle_paused(self) -> None: ...
```

- **Clock**(`show_date, show_secs, show_millis, tz`): text is `HH:MM`, `HH:MM:SS` or
  `HH:MM:SS.d`; header `YYYY-MM-DD` plus ` <tz key>` when a timezone is set.
- **Stopwatch**: wraps a shared `ElapsedClock` (accumulated ms + optional start stamp,
  pause/resume); starts running. Footer
  `PAUSED (press <SPACE> to resume)` while paused. `display_time()` returns the
  `HourMinSecDeci` string for the exit print.
- **Timer**(`durations_ms, titles, repeat, fmt, paused, auto_quit, execute`):
  `remaining()` walks checkpoints exactly as the Rust `remaining_time()` (advances through
  durations, wraps when `repeat`). Header is `titles[min(idx, len-1)]` if any titles.
  When remaining < 0: `flash = abs(remaining) % 1000 < 500`, text is the elapsed overrun
  (shown only in the flash-on phase, `None` otherwise; header and footer stay visible in
  both phases so the layout does not jump), and on the first such tick
  `execute_pending` becomes `True`. The UI runs the command and calls
  `set_execute_result(str)`; that string becomes the footer. `finished = auto_quit and
  execute_result is not None`. With an empty `execute`, the result is `""` immediately,
  so `--quit` exits on the first tick after zero.
- **Countdown**(`target, title, continue_on_zero, reverse, fmt`): remaining =
  `target - now` (negated when `reverse`). Past zero without `continue_on_zero`: blink
  `format_duration(0)` at 1 Hz (`None` in the off phase). Header is the title.
- **timefmt.format_duration(ms, fmt)**: port of the Rust function. `D:HH:MM:SS[.d]`,
  leading component unpadded, others zero-padded, `-` prefix for negatives. Minutes and
  seconds are always present; hours appear when ≥ 1 h, days when ≥ 24 h. Examples:
  5 s → `0:05`, 90 min → `1:30:00`, 25 h → `1:01:00:00`, -3 s → `-0:03`; the deci
  format appends `.d` (e.g. `0:05.3`).

## Textual UI (`tclock.ui`)

- `ClockApp(App)`; `CSS_PATH = "app.tcss"`. Layout: a `Vertical` with
  `Label#header`, `BigTime#time`, `Label#footer`, `align: center middle`; header and
  footer have one row of margin from the digits.
- `BigTime(Widget)`: holds `text: str | None`, `size: int`, `color`. `render()`
  returns a Rich `Text` from `font.render(text, size)`; `get_content_width/height`
  report `len(text) * (6*size + 2) - 2` and `5*size` so Textual centres it. If
  `text is None` it renders blank lines of the same size (keeps layout stable).
- `font.render(text, size)`: bricks glyph table for `0-9 : . -` as run-length rows
  (identical to the Rust `get_char_matrix`), scaled `size×` in both axes, glyphs
  separated by 2 blank columns, `█` on / space off. Unknown characters render as blank
  glyph-width space.
- Tick: `set_interval(0.1, self._tick)`. Each tick: `frame = self.engine.snapshot()`;
  update labels and `BigTime`; toggle screen class `-flash` (green background, black
  digits); if `frame.finished` → `self.exit()`. If the engine is a `Timer` with
  `execute_pending` and no worker running, start a `@work(thread=True)` worker that runs
  `subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace")` and
  posts back `[SUCCEED] stdout` / `[ERROR] stderr` / `[FAILED] exception`.
- Bindings: `q` quit; `space` → `engine.toggle_paused()` if `Pausable`; `c` → fresh
  `Clock` from config defaults; `w` → fresh `Stopwatch`; `t` → fresh `Timer` from config
  defaults. Ctrl+C exits cleanly via Textual.
- `--color` is applied to `BigTime` via `styles.color`.
- `ui.run(engine, style, config) -> Mode` runs the app and returns the final engine so
  `cli.main` can print stopwatch time after the terminal is restored.

## Cross-platform notes

- Timezones via `zoneinfo`; `tzdata` installed only on Windows.
- `--execute` uses `shell=True`: `/bin/sh` on POSIX, `cmd.exe` on Windows.
- Config path via `platformdirs`; README lists the path per OS.
- Only non-ASCII glyph used is `█` (U+2588).
- Stdout is written only after Textual has restored the terminal.

## Testing

`pytest`, with `pytest-asyncio` for Textual pilot tests.

- `test_timefmt.py`: table-driven `format_duration` cases (zero, seconds, minutes, hours,
  days, negatives, both formats).
- `test_parsing.py`: durations (valid units, case-insensitivity, rejects `5x`, `m5`),
  colors (all 16 names, hex, rejects `#fff`, `purple`), datetimes (five formats, rejects
  garbage), timezones (valid, invalid).
- `test_modes.py`: fake clock. Timer: single duration countdown, multi-duration
  checkpoints and title index, repeat wraparound, pause/resume accounting, flash phases,
  `execute_pending` set once, `finished` semantics with/without `auto_quit`. Stopwatch:
  run, pause, resume, `display_time`. Countdown: forward, reverse, blink phases,
  `continue_on_zero`. Clock: text variants, header with/without tz.
- `test_config.py`: full TOML → dataclasses, missing sections, missing file, malformed
  TOML warns and falls back, bad single value warns and defaults that key, CLI-over-config
  precedence, `[default] mode` selection. Uses `tmp_path` and a monkeypatched config path.
- `test_font.py`: each glyph 6×5 at size 1, 12×10 at size 2, spacing, unknown char blank,
  total width formula.
- `test_ui.py`: `App.run_test()` pilot: `q` exits; `space` toggles PAUSED footer in
  stopwatch; `t` switches to timer; `-flash` class toggles when a fake-clock timer passes
  zero; `finished` frame exits the app.
- `test_cli.py`: Typer `CliRunner`: `--help` for root and each subcommand, `--version`,
  invalid duration/color/size exit code 2 with message.

## CI and release

- `ci.yml`: on push and pull_request. Matrix `ubuntu-latest`, `macos-latest`,
  `windows-latest`, Python 3.14 via `astral-sh/setup-uv` (`enable-cache`). Steps:
  `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`,
  `uv run mypy src`, `uv run pytest`, `uv build`.
- `release.yml`: `workflow_dispatch` with input `bump` (choice: `patch` default,
  `minor`, `major`, `rc`, `stable`). Steps on `main`: `uv version --bump $BUMP`
  (updates `pyproject.toml` and `uv.lock`), read new version with
  `uv version --short`, commit `chore: release vX.Y.Z` as `github-actions[bot]`, tag
  `vX.Y.Z`, push commit and tag. Requires `contents: write`; README notes that protected
  `main` needs a PAT or ruleset bypass.
- `publish.yml`: on push of tag `v*`. `uv build`, then `pypa/gh-action-pypi-publish`
  with trusted publishing (`permissions: id-token: write`, `environment: pypi`). README
  documents the one-time trusted publisher setup on pypi.org.
- `pyproject.toml` metadata: description, readme, `license = "MIT"`,
  `license-files = ["LICENSE"]`, authors, keywords
  (`clock timer stopwatch countdown tui textual terminal`), classifiers
  (Development Status 4, Environment :: Console, Intended Audience :: End Users/Desktop,
  License :: OSI Approved :: MIT License, Operating System :: OS Independent,
  Programming Language :: Python :: 3.14, Topic :: Utilities), `[project.urls]`
  Homepage, Repository, Issues, Original (race604/clock-tui).
- Initial version `0.1.0`. `tclock --version` prints `importlib.metadata.version("tclock")`.

## Out of scope

Mouse support, additional fonts, sound/notification built-ins, config file generation
command, Windows-specific installers. Any of these can follow as separate specs.
