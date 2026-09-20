"""The optional TOML config file.

Location: ``platformdirs.user_config_path("tclock") / "config.toml"``, i.e.
``~/.config/tclock/config.toml`` on Linux, ``~/Library/Application Support/tclock/config.toml``
on macOS and ``%APPDATA%\\tclock\\config.toml`` on Windows. The schema is the one used by
the Rust clock-tui. Anything wrong in the file produces a warning and a default, never an
error.
"""

import sys
import types
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar, cast, get_args, get_origin

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import platformdirs

T = TypeVar("T")

APP_NAME = "tclock"


@dataclass(slots=True)
class DefaultConfig:
    mode: str = "clock"
    color: str = "green"
    size: int = 1


@dataclass(slots=True)
class ClockConfig:
    show_date: bool = True
    show_seconds: bool = True
    show_millis: bool = False
    timezone: str | None = None


@dataclass(slots=True)
class TimerConfig:
    durations: list[str] = field(default_factory=lambda: ["25m", "5m"])
    titles: list[str] = field(default_factory=list)
    repeat: bool = False
    show_millis: bool = True
    start_paused: bool = False
    auto_quit: bool = False
    execute: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CountdownConfig:
    time: str | None = None
    title: str | None = None
    show_millis: bool = False
    continue_on_zero: bool = False
    reverse: bool = False


@dataclass(slots=True)
class Config:
    default: DefaultConfig = field(default_factory=DefaultConfig)
    clock: ClockConfig = field(default_factory=ClockConfig)
    timer: TimerConfig = field(default_factory=TimerConfig)
    countdown: CountdownConfig = field(default_factory=CountdownConfig)


def warn_stderr(message: str) -> None:
    print(message, file=sys.stderr)


def config_path() -> Path:
    return platformdirs.user_config_path(APP_NAME) / "config.toml"


def load_config(path: Path | None = None, *, warn: Callable[[str], None] = warn_stderr) -> Config:
    """Read the config file, falling back to defaults for anything missing or wrong."""
    path = path if path is not None else config_path()
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        warn(f"tclock: ignoring {path}: {exc}")
        return Config()
    return Config(
        default=_section(DefaultConfig, data, "default", warn),
        clock=_section(ClockConfig, data, "clock", warn),
        timer=_section(TimerConfig, data, "timer", warn),
        countdown=_section(CountdownConfig, data, "countdown", warn),
    )


def _section(cls: type[T], data: dict[str, Any], name: str, warn: Callable[[str], None]) -> T:
    raw = data.get(name, {})
    result = cls()
    if not isinstance(raw, dict):
        warn(f"tclock: config section [{name}] must be a table; using defaults")
        return result
    for f in fields(cast(Any, cls)):
        if f.name not in raw:
            continue
        value = raw[f.name]
        if _matches(value, f.type):
            setattr(result, f.name, value)
        else:
            warn(f"tclock: config {name}.{f.name} has the wrong type; using the default")
    return result


def _matches(value: object, expected: Any) -> bool:
    if isinstance(expected, types.UnionType):
        return any(_matches(value, arg) for arg in get_args(expected))
    if expected is type(None):
        return value is None
    if get_origin(expected) is list:
        (item_type,) = get_args(expected)
        return isinstance(value, list) and all(_matches(item, item_type) for item in value)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)
