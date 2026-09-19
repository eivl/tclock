"""Merge CLI options with the config file and build the mode engine.

Precedence: CLI flag > config file > built-in default. CLI booleans are "set" flags, so
they can only turn a behaviour on (``flag or config_value``), matching clock-tui.
CLI values arrive already validated by the CLI layer; config values are validated here
with a warning and a fallback for each bad key.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from tclock.config import Config, warn_stderr
from tclock.modes import Clock, Countdown, Mode, Stopwatch, Timer
from tclock.parsing import ParseError, parse_color, parse_datetime, parse_duration, parse_timezone
from tclock.timefmt import DurationFormat

MODES = ("clock", "timer", "stopwatch", "countdown")

Warn = Callable[[str], None]


class ResolveError(Exception):
    """The combination of CLI options and config cannot produce a runnable mode."""


@dataclass(slots=True, kw_only=True)
class Options:
    """What the user asked for on the command line. ``None``/``False``/``[]`` = not given."""

    mode: str | None = None
    color: str | None = None
    size: int | None = None
    # clock
    timezone: str | None = None
    no_date: bool = False
    no_seconds: bool = False
    millis: bool = False
    # timer
    durations: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    repeat: bool = False
    no_millis: bool = False
    paused: bool = False
    auto_quit: bool = False
    execute: str | None = None
    # countdown
    time: str | None = None
    title: str | None = None
    continue_on_zero: bool = False
    reverse: bool = False


@dataclass(slots=True)
class Resolved:
    engine: Mode
    color: str
    size: int


def resolve(options: Options, config: Config, *, warn: Warn = warn_stderr) -> Resolved:
    mode = options.mode or config.default.mode
    if mode not in MODES:
        warn(f"tclock: unknown mode {mode!r} in config; using clock")
        mode = "clock"

    engine: Mode
    if mode == "timer":
        engine = build_timer(options, config, warn=warn)
    elif mode == "stopwatch":
        engine = build_stopwatch()
    elif mode == "countdown":
        engine = build_countdown(options, config, warn=warn)
    else:
        engine = build_clock(options, config, warn=warn)

    return Resolved(
        engine=engine, color=_color(options, config, warn), size=_size(options, config, warn)
    )


def _color(options: Options, config: Config, warn: Warn) -> str:
    if options.color is not None:
        return parse_color(options.color)
    try:
        return parse_color(config.default.color)
    except ParseError as exc:
        warn(f"tclock: config default.color: {exc}; using green")
        return parse_color("green")


def _size(options: Options, config: Config, warn: Warn) -> int:
    if options.size is not None:
        return options.size
    if config.default.size < 1:
        warn(f"tclock: config default.size must be >= 1, got {config.default.size}; using 1")
        return 1
    return config.default.size


def build_clock(options: Options, config: Config, *, warn: Warn = warn_stderr) -> Clock:
    tz: ZoneInfo | None = None
    if options.timezone is not None:
        tz = parse_timezone(options.timezone)
    elif config.clock.timezone is not None:
        try:
            tz = parse_timezone(config.clock.timezone)
        except ParseError as exc:
            warn(f"tclock: config clock.timezone: {exc}; using local time")
    return Clock(
        show_date=not options.no_date and config.clock.show_date,
        show_secs=not options.no_seconds and config.clock.show_seconds,
        show_millis=options.millis or config.clock.show_millis,
        tz=tz,
    )


def build_timer(options: Options, config: Config, *, warn: Warn = warn_stderr) -> Timer:
    if options.durations:
        durations_ms = [parse_duration(d) for d in options.durations]
    else:
        durations_ms = []
        for text in config.timer.durations:
            try:
                durations_ms.append(parse_duration(text))
            except ParseError as exc:
                warn(f"tclock: config timer.durations: {exc}; skipping it")
        if not durations_ms:
            durations_ms = [25 * 60_000, 5 * 60_000]

    show_millis = not options.no_millis and config.timer.show_millis
    execute = options.execute or " ".join(config.timer.execute) or None
    return Timer(
        durations_ms,
        titles=options.titles or config.timer.titles,
        repeat=options.repeat or config.timer.repeat,
        fmt=DurationFormat.HOUR_MIN_SEC_DECI if show_millis else DurationFormat.HOUR_MIN_SEC,
        paused=options.paused or config.timer.start_paused,
        auto_quit=options.auto_quit or config.timer.auto_quit,
        execute=execute,
    )


def build_stopwatch() -> Stopwatch:
    return Stopwatch()


def build_countdown(options: Options, config: Config, *, warn: Warn = warn_stderr) -> Countdown:
    time_text = options.time or config.countdown.time
    if time_text is None:
        raise ResolveError("countdown needs --time or a [countdown] time entry in the config file")
    try:
        target = parse_datetime(time_text)
    except ParseError as exc:
        raise ResolveError(str(exc)) from None
    show_millis = options.millis or config.countdown.show_millis
    return Countdown(
        target,
        title=options.title or config.countdown.title,
        continue_on_zero=options.continue_on_zero or config.countdown.continue_on_zero,
        reverse=options.reverse or config.countdown.reverse,
        fmt=DurationFormat.HOUR_MIN_SEC_DECI if show_millis else DurationFormat.HOUR_MIN_SEC,
    )
