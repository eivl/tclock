import pytest

from tclock.timefmt import DurationFormat, format_duration

HMS = DurationFormat.HOUR_MIN_SEC
HMSD = DurationFormat.HOUR_MIN_SEC_DECI


@pytest.mark.parametrize(
    ("ms", "fmt", "expected"),
    [
        (0, HMS, "0:00"),
        (0, HMSD, "0:00.0"),
        (5_000, HMS, "0:05"),
        (5_300, HMSD, "0:05.3"),
        (59_999, HMS, "0:59"),
        (59_999, HMSD, "0:59.9"),
        (60_000, HMS, "1:00"),
        (5 * 60_000, HMS, "5:00"),
        (90 * 60_000, HMS, "1:30:00"),
        (3_600_000, HMSD, "1:00:00.0"),
        (25 * 3_600_000, HMS, "1:01:00:00"),
        (2 * 86_400_000 + 3_600_000 + 60_000 + 1_000, HMS, "2:01:01:01"),
        (-3_000, HMS, "-0:03"),
        (-3_400, HMSD, "-0:03.4"),
        (-90 * 60_000, HMS, "-1:30:00"),
    ],
)
def test_format_duration(ms: int, fmt: DurationFormat, expected: str) -> None:
    assert format_duration(ms, fmt) == expected
