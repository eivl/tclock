"""Timer mode: counts down one or more durations, flashes when done."""

from collections.abc import Callable, Sequence

from tclock.modes.base import PAUSED_FOOTER, ElapsedClock, Frame, wall_clock_ms
from tclock.timefmt import DurationFormat, format_duration


class Timer:
    def __init__(
        self,
        durations_ms: Sequence[int],
        *,
        titles: Sequence[str] = (),
        repeat: bool = False,
        fmt: DurationFormat = DurationFormat.HOUR_MIN_SEC_DECI,
        paused: bool = False,
        auto_quit: bool = False,
        execute: str | None = None,
        now_ms: Callable[[], int] = wall_clock_ms,
    ) -> None:
        if not durations_ms:
            raise ValueError("timer needs at least one duration")
        if any(d <= 0 for d in durations_ms):
            raise ValueError("timer durations must be positive")
        self.durations_ms = list(durations_ms)
        self.titles = list(titles)
        self.repeat = repeat
        self.fmt = fmt
        self.auto_quit = auto_quit
        self.execute = execute or None
        self.execute_pending = False
        """The UI should run :attr:`execute` and call :meth:`set_execute_result`."""
        self.execute_result: str | None = None
        self._clock = ElapsedClock(now_ms, running=not paused)

    def remaining(self) -> tuple[int, int]:
        """(milliseconds left in the current duration, index of that duration).

        After the last duration (without ``repeat``) the remaining value goes negative
        and keeps counting down, so callers can show how long ago the timer ended.
        """
        passed = self._clock.elapsed_ms()
        if self.repeat:
            passed %= sum(self.durations_ms)
        idx = 0
        checkpoint = self.durations_ms[0]
        while checkpoint < passed and idx < len(self.durations_ms) - 1:
            idx += 1
            checkpoint += self.durations_ms[idx]
        return checkpoint - passed, idx

    def title(self, idx: int) -> str | None:
        if not self.titles:
            return None
        return self.titles[min(idx, len(self.titles) - 1)]

    def set_execute_result(self, result: str) -> None:
        self.execute_result = result
        self.execute_pending = False

    def is_finished(self) -> bool:
        return self.auto_quit and self.execute_result is not None

    def is_paused(self) -> bool:
        return self._clock.is_paused()

    def pause(self) -> None:
        self._clock.pause()

    def resume(self) -> None:
        self._clock.resume()

    def toggle_paused(self) -> None:
        self._clock.toggle_paused()

    def snapshot(self) -> Frame:
        remaining, idx = self.remaining()
        header = self.title(idx)
        footer = PAUSED_FOOTER if self.is_paused() else self.execute_result
        if remaining >= 0:
            return Frame(text=format_duration(remaining, self.fmt), header=header, footer=footer)

        # The timer has run out.
        if self.execute_result is None and not self.execute_pending:
            if self.execute:
                self.execute_pending = True
            else:
                self.execute_result = ""
                footer = PAUSED_FOOTER if self.is_paused() else self.execute_result
        overrun = -remaining
        flash = overrun % 1000 < 500
        return Frame(
            text=format_duration(overrun, self.fmt) if flash else None,
            header=header,
            footer=footer,
            flash=flash,
            finished=self.is_finished(),
        )
