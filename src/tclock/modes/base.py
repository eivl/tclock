"""Shared types for mode engines.

Engines are plain Python: they read an injected millisecond clock and return a
:class:`Frame` describing what the UI should show. They never import Textual.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

PAUSED_FOOTER = "PAUSED (press <SPACE> to resume)"


def wall_clock_ms() -> int:
    """Current wall-clock time in whole milliseconds."""
    return time.time_ns() // 1_000_000


@dataclass(frozen=True, slots=True)
class Frame:
    """One tick's worth of display state."""

    text: str | None
    """Digits to draw, or ``None`` to leave the digit area blank (blink-off phase)."""
    header: str | None = None
    footer: str | None = None
    flash: bool = False
    """Invert colors (green background) - used when a timer has run out."""
    finished: bool = False
    """The app should exit."""


@runtime_checkable
class Mode(Protocol):
    def snapshot(self) -> Frame: ...


@runtime_checkable
class Pausable(Protocol):
    def is_paused(self) -> bool: ...

    def toggle_paused(self) -> None: ...


class ElapsedClock:
    """Accumulates elapsed milliseconds with pause/resume."""

    def __init__(self, now_ms: Callable[[], int] = wall_clock_ms, *, running: bool = True) -> None:
        self._now = now_ms
        self._accumulated_ms = 0
        self._started_at_ms: int | None = now_ms() if running else None

    def elapsed_ms(self) -> int:
        if self._started_at_ms is None:
            return self._accumulated_ms
        return self._accumulated_ms + (self._now() - self._started_at_ms)

    def is_paused(self) -> bool:
        return self._started_at_ms is None

    def pause(self) -> None:
        if self._started_at_ms is not None:
            self._accumulated_ms += self._now() - self._started_at_ms
            self._started_at_ms = None

    def resume(self) -> None:
        if self._started_at_ms is None:
            self._started_at_ms = self._now()

    def toggle_paused(self) -> None:
        if self.is_paused():
            self.resume()
        else:
            self.pause()
