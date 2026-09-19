from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo

from tclock.modes import Clock, Frame, Pausable

FIXED = datetime(2026, 9, 19, 14, 5, 9, 730_000)


def fixed_now(tz: tzinfo | None) -> datetime:
    return FIXED if tz is None else FIXED.replace(tzinfo=tz)


def test_default_shows_seconds_and_date() -> None:
    assert Clock(now=fixed_now).snapshot() == Frame(text="14:05:09", header="2026-09-19")


def test_millis_wins_over_no_seconds() -> None:
    clock = Clock(show_secs=False, show_millis=True, now=fixed_now)
    assert clock.snapshot().text == "14:05:09.7"


def test_no_seconds_and_no_date() -> None:
    clock = Clock(show_secs=False, show_date=False, now=fixed_now)
    assert clock.snapshot() == Frame(text="14:05")


def test_timezone_in_header() -> None:
    tz = ZoneInfo("Asia/Tokyo")
    frame = Clock(tz=tz, now=fixed_now).snapshot()
    assert frame.header == "2026-09-19 Asia/Tokyo"


def test_clock_is_not_pausable() -> None:
    assert not isinstance(Clock(), Pausable)


def test_real_clock_produces_plausible_text() -> None:
    text = Clock().snapshot().text
    assert text is not None
    assert len(text) == len("HH:MM:SS")
