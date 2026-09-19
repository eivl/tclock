from tclock.modes.base import ElapsedClock, Frame, Mode, Pausable, wall_clock_ms
from tests.conftest import FakeClock


def test_frame_defaults() -> None:
    frame = Frame(text="1:00")
    assert frame == Frame("1:00", None, None, False, False)


def test_wall_clock_is_milliseconds() -> None:
    ms = wall_clock_ms()
    assert ms > 1_600_000_000_000  # after 2020


def test_elapsed_clock_runs(fake_clock: FakeClock) -> None:
    clock = ElapsedClock(fake_clock)
    assert clock.elapsed_ms() == 0
    fake_clock.advance(1500)
    assert clock.elapsed_ms() == 1500
    assert not clock.is_paused()


def test_elapsed_clock_pause_resume(fake_clock: FakeClock) -> None:
    clock = ElapsedClock(fake_clock)
    fake_clock.advance(1000)
    clock.pause()
    fake_clock.advance(5000)
    assert clock.elapsed_ms() == 1000
    assert clock.is_paused()
    clock.resume()
    fake_clock.advance(250)
    assert clock.elapsed_ms() == 1250


def test_elapsed_clock_toggle_and_idempotent_calls(fake_clock: FakeClock) -> None:
    clock = ElapsedClock(fake_clock)
    clock.resume()  # already running: no-op
    fake_clock.advance(100)
    clock.toggle_paused()
    clock.pause()  # already paused: no-op
    fake_clock.advance(100)
    assert clock.elapsed_ms() == 100
    clock.toggle_paused()
    fake_clock.advance(100)
    assert clock.elapsed_ms() == 200


def test_elapsed_clock_can_start_paused(fake_clock: FakeClock) -> None:
    clock = ElapsedClock(fake_clock, running=False)
    fake_clock.advance(999)
    assert clock.elapsed_ms() == 0
    assert clock.is_paused()


def test_protocols_are_runtime_checkable(fake_clock: FakeClock) -> None:
    class Dummy:
        def snapshot(self) -> Frame:
            return Frame(text=None)

    assert isinstance(Dummy(), Mode)
    assert not isinstance(Dummy(), Pausable)
    assert isinstance(ElapsedClock(fake_clock), Pausable)
