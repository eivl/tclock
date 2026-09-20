"""Parsers for CLI and config values. All failures raise :class:`ParseError`."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ParseError(ValueError):
    """A user-supplied value could not be interpreted."""


_DURATION_RE = re.compile(r"^(\d+)([smhd])$", re.IGNORECASE)
_UNIT_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}

_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")

# clock-tui color names -> Textual color strings (ratatui's 16 ANSI colors).
COLOR_NAMES: dict[str, str] = {
    "black": "ansi_black",
    "red": "ansi_red",
    "green": "ansi_green",
    "yellow": "ansi_yellow",
    "blue": "ansi_blue",
    "magenta": "ansi_magenta",
    "cyan": "ansi_cyan",
    "gray": "ansi_white",
    "darkgray": "ansi_bright_black",
    "lightred": "ansi_bright_red",
    "lightgreen": "ansi_bright_green",
    "lightyellow": "ansi_bright_yellow",
    "lightblue": "ansi_bright_blue",
    "lightmagenta": "ansi_bright_magenta",
    "lightcyan": "ansi_bright_cyan",
    "white": "ansi_bright_white",
}

_NAIVE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S")
_TIME_FORMATS = ("%H:%M", "%H:%M:%S")


def parse_duration(text: str) -> int:
    """``10s``, ``5m``, ``1h``, ``2d`` (case-insensitive) -> milliseconds."""
    match = _DURATION_RE.match(text)
    if match is None:
        raise ParseError(f"{text!r} is not a valid duration (examples: 30s, 5m, 1h, 2d)")
    number, unit = match.groups()
    return int(number) * _UNIT_MS[unit.lower()]


def parse_color(text: str) -> str:
    """A clock-tui color name or ``#rrggbb`` -> Textual color string."""
    lowered = text.strip().lower()
    if lowered in COLOR_NAMES:
        return COLOR_NAMES[lowered]
    if _HEX_RE.match(lowered):
        return lowered
    names = ", ".join(COLOR_NAMES)
    raise ParseError(f"{text!r} is not a valid color; use #rrggbb or one of: {names}")


def parse_datetime(text: str, *, today: date | None = None) -> datetime:
    """Parse ``HH:MM``, ``HH:MM:SS``, ``YYYY-MM-DD``, ``YYYY-MM-DD HH:MM:SS`` or RFC 3339.

    Naive forms are interpreted in the local timezone. The result is always aware.
    """
    text = text.strip()
    today = today or datetime.now().date()
    for fmt in _TIME_FORMATS:
        try:
            parsed_time = datetime.strptime(text, fmt).time()
        except ValueError:
            continue
        return datetime.combine(today, parsed_time).astimezone()
    for fmt in _NAIVE_FORMATS:
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ParseError(
            f"{text!r} is not a valid time; use HH:MM, YYYY-MM-DD, "
            "'YYYY-MM-DD HH:MM:SS' or RFC 3339"
        ) from None
    return parsed.astimezone()


def parse_timezone(text: str) -> ZoneInfo:
    """An IANA zone key such as ``Europe/Oslo``."""
    try:
        return ZoneInfo(text.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise ParseError(f"{text!r} is not a known timezone (example: Europe/Oslo)") from None
