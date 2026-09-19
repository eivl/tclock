from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tclock.config import Config
from tclock.modes import Clock, Countdown, Stopwatch, Timer
from tclock.resolve import Options, ResolveError, build_timer, resolve
from tclock.timefmt import DurationFormat


def test_defaults_give_green_clock_size_1() -> None:
    r = resolve(Options(), Config(), warn=pytest.fail)
    assert isinstance(r.engine, Clock)
    assert (r.color, r.size) == ("ansi_green", 1)
    assert r.engine.show_date and r.engine.show_secs and not r.engine.show_millis


def test_cli_color_and_size_beat_config() -> None:
    config = Config()
    config.default.color = "yellow"
    config.default.size = 3
    r = resolve(Options(color="#e63946", size=2), config, warn=pytest.fail)
    assert (r.color, r.size) == ("#e63946", 2)
    r = resolve(Options(), config, warn=pytest.fail)
    assert (r.color, r.size) == ("ansi_yellow", 3)


def test_bad_config_color_and_size_warn_and_default() -> None:
    config = Config()
    config.default.color = "purple"
    config.default.size = 0
    warnings: list[str] = []
    r = resolve(Options(), config, warn=warnings.append)
    assert (r.color, r.size) == ("ansi_green", 1)
    assert len(warnings) == 2


def test_config_default_mode_selects_engine() -> None:
    config = Config()
    config.default.mode = "stopwatch"
    assert isinstance(resolve(Options(), config, warn=pytest.fail).engine, Stopwatch)
    config.default.mode = "timer"
    assert isinstance(resolve(Options(), config, warn=pytest.fail).engine, Timer)


def test_unknown_config_mode_warns_and_uses_clock() -> None:
    config = Config()
    config.default.mode = "sundial"
    warnings: list[str] = []
    assert isinstance(resolve(Options(), config, warn=warnings.append).engine, Clock)
    assert warnings and "sundial" in warnings[0]


def test_clock_flags_merge_with_config() -> None:
    config = Config()
    config.clock.show_seconds = False
    config.clock.timezone = "Asia/Tokyo"
    clock = resolve(Options(mode="clock", no_date=True), config, warn=pytest.fail).engine
    assert isinstance(clock, Clock)
    assert clock.show_date is False
    assert clock.show_secs is False
    assert clock.tz == ZoneInfo("Asia/Tokyo")
    clock = resolve(Options(mode="clock", timezone="Europe/Oslo"), config, warn=pytest.fail).engine
    assert isinstance(clock, Clock)
    assert clock.tz == ZoneInfo("Europe/Oslo")


def test_bad_config_timezone_warns() -> None:
    config = Config()
    config.clock.timezone = "Mars/Base"
    warnings: list[str] = []
    clock = resolve(Options(mode="clock"), config, warn=warnings.append).engine
    assert isinstance(clock, Clock) and clock.tz is None
    assert len(warnings) == 1


def test_timer_from_config_defaults() -> None:
    timer = build_timer(Options(), Config(), warn=pytest.fail)
    assert timer.durations_ms == [25 * 60_000, 5 * 60_000]
    assert timer.fmt is DurationFormat.HOUR_MIN_SEC_DECI
    assert timer.execute is None


def test_timer_cli_beats_config() -> None:
    config = Config()
    config.timer.durations = ["50m"]
    config.timer.titles = ["Config"]
    config.timer.execute = ["notify-send", "done"]
    config.timer.show_millis = True
    opts = Options(
        mode="timer",
        durations=["1m", "2m"],
        titles=["A"],
        no_millis=True,
        repeat=True,
        paused=True,
        auto_quit=True,
        execute="echo hi",
    )
    timer = resolve(opts, config, warn=pytest.fail).engine
    assert isinstance(timer, Timer)
    assert timer.durations_ms == [60_000, 120_000]
    assert timer.titles == ["A"]
    assert timer.fmt is DurationFormat.HOUR_MIN_SEC
    assert timer.repeat and timer.is_paused() and timer.auto_quit
    assert timer.execute == "echo hi"


def test_timer_config_execute_list_is_joined() -> None:
    config = Config()
    config.timer.execute = ["notify-send", "-t", "5", "done"]
    config.timer.show_millis = False
    timer = build_timer(Options(), config, warn=pytest.fail)
    assert timer.execute == "notify-send -t 5 done"
    assert timer.fmt is DurationFormat.HOUR_MIN_SEC


def test_timer_bad_config_durations_warn_and_fall_back() -> None:
    config = Config()
    config.timer.durations = ["nope", "5x"]
    warnings: list[str] = []
    timer = build_timer(Options(), config, warn=warnings.append)
    assert timer.durations_ms == [25 * 60_000, 5 * 60_000]
    assert len(warnings) == 2


def test_countdown_requires_a_time() -> None:
    with pytest.raises(ResolveError):
        resolve(Options(mode="countdown"), Config(), warn=pytest.fail)


def test_countdown_from_cli_and_config() -> None:
    config = Config()
    config.countdown.time = "2027-01-01"
    config.countdown.title = "Config title"
    config.countdown.show_millis = True
    cd = resolve(Options(mode="countdown"), config, warn=pytest.fail).engine
    assert isinstance(cd, Countdown)
    assert cd.target_ms == int(datetime(2027, 1, 1).astimezone().timestamp() * 1000)
    assert cd.title == "Config title"
    assert cd.fmt is DurationFormat.HOUR_MIN_SEC_DECI
    cd = resolve(
        Options(
            mode="countdown", time="2028-01-01", title="CLI", reverse=True, continue_on_zero=True
        ),
        config,
        warn=pytest.fail,
    ).engine
    assert isinstance(cd, Countdown)
    assert cd.title == "CLI" and cd.reverse and cd.continue_on_zero
    assert cd.target_ms == int(datetime(2028, 1, 1).astimezone().timestamp() * 1000)


def test_countdown_bad_config_time_is_an_error() -> None:
    config = Config()
    config.countdown.time = "someday"
    with pytest.raises(ResolveError):
        resolve(Options(mode="countdown"), config, warn=pytest.fail)
