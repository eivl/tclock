from pathlib import Path

import pytest

from tclock import config as cfg

FULL = """
[default]
mode = "timer"
color = "yellow"
size = 2

[clock]
show_date = false
show_seconds = false
show_millis = true
timezone = "Europe/Oslo"

[timer]
durations = ["50m", "10m"]
titles = ["Focus", "Rest"]
repeat = true
show_millis = false
start_paused = true
auto_quit = true
execute = ["notify-send", "done"]

[stopwatch]

[countdown]
time = "2027-01-01"
title = "New year"
show_millis = true
continue_on_zero = true
reverse = true
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_match_rust_tool() -> None:
    c = cfg.Config()
    assert c.default == cfg.DefaultConfig(mode="clock", color="green", size=1)
    assert c.clock == cfg.ClockConfig(show_date=True, show_seconds=True, show_millis=False)
    assert c.timer.durations == ["25m", "5m"]
    assert c.timer.show_millis is True
    assert c.countdown == cfg.CountdownConfig()


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    warnings: list[str] = []
    assert cfg.load_config(tmp_path / "nope.toml", warn=warnings.append) == cfg.Config()
    assert warnings == []


def test_full_file(tmp_path: Path) -> None:
    c = cfg.load_config(write(tmp_path, FULL), warn=lambda m: pytest.fail(m))
    assert c.default == cfg.DefaultConfig(mode="timer", color="yellow", size=2)
    assert c.clock == cfg.ClockConfig(
        show_date=False, show_seconds=False, show_millis=True, timezone="Europe/Oslo"
    )
    assert c.timer == cfg.TimerConfig(
        durations=["50m", "10m"],
        titles=["Focus", "Rest"],
        repeat=True,
        show_millis=False,
        start_paused=True,
        auto_quit=True,
        execute=["notify-send", "done"],
    )
    assert c.countdown == cfg.CountdownConfig(
        time="2027-01-01", title="New year", show_millis=True, continue_on_zero=True, reverse=True
    )


def test_partial_file_keeps_other_defaults(tmp_path: Path) -> None:
    c = cfg.load_config(write(tmp_path, '[default]\ncolor = "red"\n'), warn=pytest.fail)
    assert c.default.color == "red"
    assert c.default.size == 1
    assert c.timer.durations == ["25m", "5m"]


def test_malformed_toml_warns_and_uses_defaults(tmp_path: Path) -> None:
    warnings: list[str] = []
    c = cfg.load_config(write(tmp_path, "[default\nmode = "), warn=warnings.append)
    assert c == cfg.Config()
    assert len(warnings) == 1
    assert "config.toml" in warnings[0]


def test_wrong_type_warns_for_that_key_only(tmp_path: Path) -> None:
    warnings: list[str] = []
    text = '[default]\nsize = "big"\ncolor = "red"\n[timer]\ndurations = "25m"\nrepeat = 1\n'
    c = cfg.load_config(write(tmp_path, text), warn=warnings.append)
    assert c.default.size == 1
    assert c.default.color == "red"
    assert c.timer.durations == ["25m", "5m"]
    assert c.timer.repeat is False
    assert len(warnings) == 3
    assert any("default.size" in w for w in warnings)
    assert any("timer.durations" in w for w in warnings)
    assert any("timer.repeat" in w for w in warnings)


def test_unknown_keys_and_sections_are_ignored(tmp_path: Path) -> None:
    c = cfg.load_config(write(tmp_path, "[default]\nfoo = 1\n[extra]\nbar = 2\n"), warn=pytest.fail)
    assert c == cfg.Config()


def test_config_path_uses_platformdirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cfg.platformdirs, "user_config_path", lambda appname: tmp_path / appname)
    assert cfg.config_path() == tmp_path / "tclock" / "config.toml"


def test_load_config_defaults_to_config_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = write(tmp_path, '[default]\nmode = "stopwatch"\n')
    monkeypatch.setattr(cfg, "config_path", lambda: path)
    assert cfg.load_config().default.mode == "stopwatch"
