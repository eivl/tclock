from dataclasses import fields
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


# --- Template ------------------------------------------------------------------------------


def _uncommented(template: str) -> str:
    """Turn every '# key = value' line into 'key = value', keeping other comments."""
    out = []
    for line in template.splitlines():
        stripped = line[2:] if line.startswith("# ") else line
        out.append(stripped if " = " in stripped and not stripped.startswith("#") else line)
    return "\n".join(out) + "\n"


def test_template_loads_as_pure_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(cfg.render_template(path), encoding="utf-8")
    warnings: list[str] = []
    assert cfg.load_config(path, warn=warnings.append) == cfg.Config()
    assert warnings == []


def test_template_lists_every_key_once_per_section() -> None:
    template = cfg.render_template(Path("/x/config.toml"))
    blocks = {block.split("]\n", 1)[0]: block for block in template.split("\n[")[1:]}
    for section_field in fields(cfg.Config()):
        block = blocks[section_field.name]
        section = getattr(cfg.Config(), section_field.name)
        for key_field in fields(section):
            assert block.count(f"\n# {key_field.name} = ") == 1, key_field.name
    assert len(blocks) == len(fields(cfg.Config()))


def test_template_uncommented_round_trips_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(_uncommented(cfg.render_template(path)), encoding="utf-8")
    warnings: list[str] = []
    loaded = cfg.load_config(path, warn=warnings.append)
    assert warnings == []
    # Keys that are unset by default carry an example value; everything else is the default.
    assert loaded.clock.timezone == "Europe/Oslo"
    assert loaded.countdown.time == "2027-01-01"
    assert loaded.countdown.title == "New year"
    loaded.clock.timezone = None
    loaded.countdown.time = None
    loaded.countdown.title = None
    assert loaded == cfg.Config()


def test_template_mentions_path_and_help(tmp_path: Path) -> None:
    template = cfg.render_template(tmp_path / "config.toml")
    assert f"# Location: {tmp_path / 'config.toml'}" in template
    assert "# Digit size, a positive integer\n# size = 1\n" in template
    assert "(unset by default)\n# timezone = " in template


def test_every_key_has_help_and_unset_keys_have_examples() -> None:
    for section_field in fields(cfg.Config()):
        section = getattr(cfg.Config(), section_field.name)
        for key_field in fields(section):
            assert key_field.name in cfg.KEY_HELP[section_field.name]
            if getattr(section, key_field.name) is None:
                assert key_field.name in cfg.EXAMPLES[section_field.name]


def test_write_template_creates_parents_and_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "config.toml"
    assert cfg.write_template(path) == path
    assert path.read_text(encoding="utf-8") == cfg.render_template(path)
    path.write_text("custom = 1\n", encoding="utf-8")
    with pytest.raises(cfg.ConfigExistsError):
        cfg.write_template(path)
    assert path.read_text(encoding="utf-8") == "custom = 1\n"
    cfg.write_template(path, force=True)
    assert path.read_text(encoding="utf-8") == cfg.render_template(path)


def test_write_template_defaults_to_config_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cfg, "config_path", lambda: tmp_path / "config.toml")
    assert cfg.write_template() == tmp_path / "config.toml"
    assert (tmp_path / "config.toml").is_file()
