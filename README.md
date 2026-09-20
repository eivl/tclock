# tclock

A clock, timer, stopwatch and countdown for your terminal, drawn with big block digits.
Built with [Textual](https://textual.textualize.io/). A Python port of
[race604/clock-tui](https://github.com/race604/clock-tui).

Works on Linux, macOS and Windows. Requires Python 3.14 or newer.

## Install

```shell
uv tool install tclock
# or
pipx install tclock
# or
pip install tclock
```

## Usage

```shell
tclock                 # clock (default mode)
tclock clock -z Asia/Tokyo -D      # another timezone, no date line
tclock timer -d 25m -d 5m -t Work -t Break -r
tclock stopwatch
tclock countdown -t 2027-01-01 -T "New year"
tclock -c '#e63946' -s 2           # colour and size apply to every mode
```

Keys while running:

| Key              | Action                                 |
|------------------|----------------------------------------|
| `q`, `Ctrl+C`    | quit                                   |
| `Space`          | pause / resume (timer and stopwatch)   |
| `c`              | switch to clock                        |
| `w`              | switch to stopwatch                    |
| `t`              | switch to timer (defaults from config) |
| `?`              | show / hide the key overlay            |

A key bar with the same bindings appears along the bottom whenever you touch the keyboard
or mouse and fades out after a few seconds, so the clock stays clean at rest.

Run `tclock --help` or `tclock <mode> --help` for every flag.

### Clock

`tclock clock [-z TZ] [-D] [-S] [-m]` shows the current time. `-z` takes an IANA zone such
as `Europe/Oslo`. `-D` hides the date, `-S` hides seconds, `-m` shows tenths of a second.

### Timer

`tclock timer -d 5m` counts down five minutes. Durations are a number plus `s`, `m`, `h`
or `d`. Repeat `-d` to run several durations in sequence and `-t` to title each of them.
`-r` repeats the sequence, `-P` starts paused, `-Q` quits when time is up, `-M` hides
tenths.

`-e` runs a shell command when the timer ends and shows its result in the footer:

```shell
tclock timer -d 25m -e 'notify-send tclock "Time is up"'      # Linux
tclock timer -d 25m -e 'osascript -e "display notification \"Time is up\""'   # macOS
tclock timer -d 25m -e 'msg * Time is up'                       # Windows
```

When the timer runs out the screen flashes green until you quit or switch mode.

### Stopwatch

`tclock stopwatch` counts up. Press `Space` to pause. The final time is printed to the
terminal after you quit.

### Countdown

`tclock countdown -t WHEN [-T TITLE] [-c] [-r] [-m]` shows the time until `WHEN`, which
can be `20:00`, `20:00:00` (today), `2027-01-01` (midnight), `2026-12-25 20:00:00` (local
time) or RFC 3339 such as `2026-12-25T20:00:00-04:00`. `-c` keeps counting (negative)
after the moment has passed instead of blinking `0:00`; `-r` counts up since the moment.

## Configuration

tclock reads an optional TOML file:

| OS      | Path                                                        |
|---------|-------------------------------------------------------------|
| Linux   | `~/.config/tclock/config.toml` (honours `$XDG_CONFIG_HOME`) |
| macOS   | `~/Library/Application Support/tclock/config.toml`          |
| Windows | `%APPDATA%\tclock\config.toml`                              |

Command-line flags override the file; the file overrides built-in defaults. Every key is
optional. The full schema, with the built-in defaults:

```toml
[default]
mode = "clock"          # clock, timer, stopwatch or countdown when no mode is given
color = "green"
size = 1

[clock]
show_date = true
show_seconds = true
show_millis = false
# timezone = "Europe/Oslo"

[timer]
durations = ["25m", "5m"]
titles = []
repeat = false
show_millis = true
start_paused = false
auto_quit = false
execute = []            # joined with spaces into one shell command

[countdown]
# time = "2027-01-01"
# title = "New year"
show_millis = false
continue_on_zero = false
reverse = false
```

A broken file or a wrong value produces a warning on stderr and the default is used.

## Differences from the Rust clock-tui

- Flags that took several values now repeat instead: `-d 25m -d 5m`, `-t Work -t Break`.
- `--execute` takes one quoted shell string instead of a list of words.
- The config file lives in the platform-native location listed above rather than always
  in `~/.config/tclock/`.
- `tclock timer` without `-d` uses the `[timer] durations` from the config file
  (`25m`, `5m` by default) instead of a fixed `5m`.
- `tclock countdown` without `--time` falls back to `[countdown] time` in the config file.
- `Ctrl+C` quits. In the Rust binary it switches to clock mode, because its key matcher
  ignores the Ctrl modifier (so `Ctrl+Q`, `Ctrl+W` and `Ctrl+T` also act like the plain
  letters there).
- Mode keys work from every mode. In the Rust binary a widget, once created, stays in a
  fixed priority order (clock > timer > stopwatch > countdown), so e.g. `t` from the
  clock has no visible effect and `w` from a timer keeps showing the timer.
- The `?` help overlay and the auto-hiding key bar are additions.

## Development

```shell
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run tclock
```

## Releasing

There is no manual release step. Every pull request merged into `main` is released to
[PyPI](https://pypi.org/project/tclock/) and gets a GitHub release with generated notes.
Control what happens with labels on the pull request:

| Label           | Effect                                        |
| --------------- | --------------------------------------------- |
| *(none)*        | Patch release, for example `0.1.4` to `0.1.5` |
| `release:minor` | Minor release, `0.1.5` to `0.2.0`             |
| `release:major` | Major release, `0.2.0` to `1.0.0`             |
| `skip-release`  | Merge without releasing, for docs or CI work  |

Release notes are grouped by the PR's other labels (`enhancement`, `bug`, `documentation`,
`ci`, `dependencies`). Pre-release bumps (`rc`, `stable`) are run by hand from the
**Release** workflow in the Actions tab. Never bump the version or push tags manually.

## License

MIT. Original clock-tui by Race604, also MIT.
