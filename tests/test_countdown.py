from datetime import datetime, timezone

from tclock.modes import Countdown, Frame
from tclock.timefmt import DurationFormat
from tests.conftest import FakeClock

TARGET = datetime(2026, 1, 1, tzinfo=timezone.utc)
TARGET_MS = int(TARGET.timestamp() * 1000)


def test_counts_down_to_target(fake_clock: FakeClock) -> None:
    fake_clock.ms = TARGET_MS - 90 * 60_000
    cd = Countdown(TARGET, title="New year", now_ms=fake_clock)
    assert cd.snapshot() == Frame(text="1:30:00", header="New year")


def test_naive_target_is_treated_as_local(fake_clock: FakeClock) -> None:
    naive = datetime(2026, 1, 1)
    cd = Countdown(naive, now_ms=fake_clock)
    assert cd.target_ms == int(naive.astimezone().timestamp() * 1000)


def test_blinks_zero_after_target(fake_clock: FakeClock) -> None:
    cd = Countdown(TARGET, now_ms=fake_clock)
    fake_clock.ms = TARGET_MS + 200
    assert cd.snapshot() == Frame(text=None)
    fake_clock.ms = TARGET_MS + 700
    assert cd.snapshot() == Frame(text="0:00")


def test_continue_on_zero_counts_negative(fake_clock: FakeClock) -> None:
    cd = Countdown(TARGET, continue_on_zero=True, now_ms=fake_clock)
    fake_clock.ms = TARGET_MS + 61_000
    assert cd.snapshot() == Frame(text="-1:01")


def test_reverse_counts_up_since_target(fake_clock: FakeClock) -> None:
    cd = Countdown(TARGET, reverse=True, fmt=DurationFormat.HOUR_MIN_SEC_DECI, now_ms=fake_clock)
    fake_clock.ms = TARGET_MS + 61_500
    assert cd.snapshot() == Frame(text="1:01.5")
