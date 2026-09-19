"""Countdown mode: time until (or, reversed, since) a fixed moment."""

from collections.abc import Callable
from datetime import datetime

from tclock.modes.base import Frame, wall_clock_ms
from tclock.timefmt import DurationFormat, format_duration


class Countdown:
    def __init__(
        self,
        target: datetime,
        *,
        title: str | None = None,
        continue_on_zero: bool = False,
        reverse: bool = False,
        fmt: DurationFormat = DurationFormat.HOUR_MIN_SEC,
        now_ms: Callable[[], int] = wall_clock_ms,
    ) -> None:
        if target.tzinfo is None:
            target = target.astimezone()
        self.target_ms = int(target.timestamp() * 1000)
        self.title = title
        self.continue_on_zero = continue_on_zero
        self.reverse = reverse
        self.fmt = fmt
        self._now = now_ms

    def remaining_ms(self) -> int:
        remaining = self.target_ms - self._now()
        return -remaining if self.reverse else remaining

    def snapshot(self) -> Frame:
        remaining = self.remaining_ms()
        if remaining < 0 and not self.continue_on_zero:
            # Blink "0:00" at 1 Hz once the moment has passed.
            if (-remaining) % 1000 < 500:
                return Frame(text=None, header=self.title)
            return Frame(text=format_duration(0, self.fmt), header=self.title)
        return Frame(text=format_duration(remaining, self.fmt), header=self.title)
