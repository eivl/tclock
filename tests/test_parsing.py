from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tclock.parsing import (
    COLOR_NAMES,
    ParseError,
    parse_color,
    parse_datetime,
    parse_duration,
    parse_timezone,
)


@pytest.mark.parametrize(
    ("text", "ms"),
    [("10s", 10_000), ("5m", 300_000), ("1h", 3_600_000), ("2d", 172_800_000), ("3M", 180_000)],
)
def test_parse_duration(text: str, ms: int) -> None:
    assert parse_duration(text) == ms


@pytest.mark.parametrize("text", ["5x", "m5", "5", "", "5 m", "-5m", "1.5h"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(ParseError):
        parse_duration(text)


def test_all_sixteen_color_names() -> None:
    names = [
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "gray",
        "darkgray", "lightred", "lightgreen", "lightyellow", "lightblue",
        "lightmagenta", "lightcyan", "white",
    ]  # fmt: skip
    assert sorted(COLOR_NAMES) == sorted(names)
    for name in names:
        assert parse_color(name).startswith("ansi_")


def test_color_name_mapping_and_case() -> None:
    assert parse_color("Red") == "ansi_red"
    assert parse_color("LightRed") == "ansi_bright_red"
    assert parse_color("gray") == "ansi_white"
    assert parse_color("darkgray") == "ansi_bright_black"
    assert parse_color("white") == "ansi_bright_white"


def test_color_hex() -> None:
    assert parse_color("#E63946") == "#e63946"


@pytest.mark.parametrize("text", ["#fff", "purple", "e63946", "#ggggggg", ""])
def test_color_rejects(text: str) -> None:
    with pytest.raises(ParseError):
        parse_color(text)


TODAY = date(2026, 9, 19)


def test_parse_datetime_time_only_uses_today_local() -> None:
    dt = parse_datetime("20:00", today=TODAY)
    assert dt.tzinfo is not None
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second) == (2026, 9, 19, 20, 0, 0)
    dt = parse_datetime("20:15:30", today=TODAY)
    assert (dt.hour, dt.minute, dt.second) == (20, 15, 30)


def test_parse_datetime_date_only_is_midnight() -> None:
    dt = parse_datetime("2027-01-01", today=TODAY)
    assert (dt.year, dt.month, dt.day, dt.hour, dt.minute) == (2027, 1, 1, 0, 0)
    assert dt.tzinfo is not None


def test_parse_datetime_date_and_time() -> None:
    dt = parse_datetime("2026-12-25 20:00:00", today=TODAY)
    assert (dt.month, dt.day, dt.hour) == (12, 25, 20)


def test_parse_datetime_rfc3339_keeps_instant() -> None:
    dt = parse_datetime("2026-12-25T20:00:00-04:00", today=TODAY)
    expected = datetime(2026, 12, 25, 20, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert dt == expected
    assert dt.tzinfo is not None


def test_parse_datetime_strips_whitespace() -> None:
    assert parse_datetime("  2027-01-01 ", today=TODAY).year == 2027


@pytest.mark.parametrize("text", ["tomorrow", "25:00", "2026/01/01", ""])
def test_parse_datetime_rejects(text: str) -> None:
    with pytest.raises(ParseError):
        parse_datetime(text, today=TODAY)


def test_parse_timezone() -> None:
    assert parse_timezone("Europe/Oslo") == ZoneInfo("Europe/Oslo")
    with pytest.raises(ParseError):
        parse_timezone("Mars/Olympus_Mons")
