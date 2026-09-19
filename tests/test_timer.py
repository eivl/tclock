import pytest

from tclock.modes import Frame, Pausable, Timer
from tclock.modes.base import PAUSED_FOOTER
from tclock.timefmt import DurationFormat
from tests.conftest import FakeClock

HMS = DurationFormat.HOUR_MIN_SEC


def test_requires_positive_durations(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError):
        Timer([], now_ms=fake_clock)
    with pytest.raises(ValueError):
        Timer([0], now_ms=fake_clock)


def test_counts_down_single_duration(fake_clock: FakeClock) -> None:
    timer = Timer([5_000], fmt=HMS, now_ms=fake_clock)
    assert timer.snapshot() == Frame(text="0:05")
    fake_clock.advance(1_500)
    assert timer.remaining() == (3_500, 0)
    assert timer.snapshot() == Frame(text="0:03")


def test_multiple_durations_and_titles(fake_clock: FakeClock) -> None:
    timer = Timer([10_000, 5_000], titles=["Work", "Break"], fmt=HMS, now_ms=fake_clock)
    assert timer.snapshot() == Frame(text="0:10", header="Work")
    fake_clock.advance(12_000)
    assert timer.remaining() == (3_000, 1)
    assert timer.snapshot() == Frame(text="0:03", header="Break")


def test_fewer_titles_than_durations_reuses_last(fake_clock: FakeClock) -> None:
    timer = Timer([1_000, 1_000, 1_000], titles=["A"], now_ms=fake_clock)
    fake_clock.advance(2_500)
    assert timer.title(timer.remaining()[1]) == "A"


def test_repeat_wraps_around(fake_clock: FakeClock) -> None:
    timer = Timer([2_000, 1_000], repeat=True, fmt=HMS, now_ms=fake_clock)
    fake_clock.advance(3_500)  # one full cycle (3s) + 0.5s into the first duration again
    assert timer.remaining() == (1_500, 0)
    fake_clock.advance(2_000)  # 5.5s: 0.5s into the second duration
    assert timer.remaining() == (500, 1)
    assert timer.snapshot().flash is False


def test_overrun_flashes_and_shows_elapsed(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], fmt=HMS, now_ms=fake_clock)
    fake_clock.advance(1_200)  # 200 ms over: on-phase
    frame = timer.snapshot()
    assert frame.flash is True
    assert frame.text == "0:00"
    fake_clock.advance(500)  # 700 ms over: off-phase
    frame = timer.snapshot()
    assert frame.flash is False
    assert frame.text is None
    fake_clock.advance(400)  # 1100 ms over: on-phase again, shows 1 s elapsed
    frame = timer.snapshot()
    assert frame.flash is True
    assert frame.text == "0:01"


def test_no_execute_finishes_immediately_with_auto_quit(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], auto_quit=True, now_ms=fake_clock)
    fake_clock.advance(999)
    assert timer.snapshot().finished is False
    fake_clock.advance(2)
    assert timer.snapshot().finished is True
    assert timer.execute_pending is False
    assert timer.execute_result == ""


def test_without_auto_quit_never_finishes(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], now_ms=fake_clock)
    fake_clock.advance(5_000)
    assert timer.snapshot().finished is False


def test_execute_requested_once_then_result_in_footer(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], execute="echo hi", auto_quit=True, now_ms=fake_clock)
    fake_clock.advance(1_100)
    frame = timer.snapshot()
    assert timer.execute_pending is True
    assert frame.finished is False
    assert frame.footer is None
    timer.snapshot()
    assert timer.execute_pending is True  # still pending, not re-requested
    timer.set_execute_result("[SUCCEED] hi")
    assert timer.execute_pending is False
    frame = timer.snapshot()
    assert frame.footer == "[SUCCEED] hi"
    assert frame.finished is True


def test_pause_freezes_and_shows_footer(fake_clock: FakeClock) -> None:
    timer = Timer([5_000], fmt=HMS, now_ms=fake_clock)
    fake_clock.advance(1_000)
    timer.toggle_paused()
    fake_clock.advance(10_000)
    assert timer.snapshot() == Frame(text="0:04", footer=PAUSED_FOOTER)
    assert isinstance(timer, Pausable)


def test_can_start_paused(fake_clock: FakeClock) -> None:
    timer = Timer([5_000], paused=True, fmt=HMS, now_ms=fake_clock)
    fake_clock.advance(3_000)
    assert timer.snapshot() == Frame(text="0:05", footer=PAUSED_FOOTER)
