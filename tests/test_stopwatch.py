from tclock.modes import Frame, Pausable, Stopwatch
from tclock.modes.base import PAUSED_FOOTER
from tests.conftest import FakeClock


def test_starts_running(fake_clock: FakeClock) -> None:
    sw = Stopwatch(now_ms=fake_clock)
    fake_clock.advance(65_400)
    assert sw.snapshot() == Frame(text="1:05.4")
    assert sw.display_time() == "1:05.4"


def test_pause_shows_footer_and_freezes(fake_clock: FakeClock) -> None:
    sw = Stopwatch(now_ms=fake_clock)
    fake_clock.advance(2_000)
    sw.toggle_paused()
    fake_clock.advance(9_000)
    assert sw.snapshot() == Frame(text="0:02.0", footer=PAUSED_FOOTER)
    sw.toggle_paused()
    fake_clock.advance(1_000)
    assert sw.snapshot() == Frame(text="0:03.0")


def test_is_pausable(fake_clock: FakeClock) -> None:
    assert isinstance(Stopwatch(now_ms=fake_clock), Pausable)
