"""Stopwatch mode: counts up from zero, pausable with Space."""

from collections.abc import Callable

from tclock.modes.base import PAUSED_FOOTER, ElapsedClock, Frame, wall_clock_ms
from tclock.timefmt import DurationFormat, format_duration


class Stopwatch:
    def __init__(self, *, now_ms: Callable[[], int] = wall_clock_ms) -> None:
        self._clock = ElapsedClock(now_ms)

    def elapsed_ms(self) -> int:
        return self._clock.elapsed_ms()

    def display_time(self) -> str:
        return format_duration(self.elapsed_ms(), DurationFormat.HOUR_MIN_SEC_DECI)

    def is_paused(self) -> bool:
        return self._clock.is_paused()

    def pause(self) -> None:
        self._clock.pause()

    def resume(self) -> None:
        self._clock.resume()

    def toggle_paused(self) -> None:
        self._clock.toggle_paused()

    def snapshot(self) -> Frame:
        footer = PAUSED_FOOTER if self.is_paused() else None
        return Frame(text=self.display_time(), footer=footer)
