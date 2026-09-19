"""Clock mode: the current time, optionally in another timezone."""

from collections.abc import Callable
from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo

from tclock.modes.base import Frame


class Clock:
    def __init__(
        self,
        *,
        show_date: bool = True,
        show_secs: bool = True,
        show_millis: bool = False,
        tz: ZoneInfo | None = None,
        now: Callable[[tzinfo | None], datetime] = datetime.now,
    ) -> None:
        self.show_date = show_date
        self.show_secs = show_secs
        self.show_millis = show_millis
        self.tz = tz
        self._now = now

    def snapshot(self) -> Frame:
        now = self._now(self.tz)
        if self.show_millis:
            text = f"{now:%H:%M:%S}.{now.microsecond // 100_000}"
        elif self.show_secs:
            text = f"{now:%H:%M:%S}"
        else:
            text = f"{now:%H:%M}"
        header = None
        if self.show_date:
            header = f"{now:%Y-%m-%d}"
            if self.tz is not None:
                header += f" {self.tz.key}"
        return Frame(text=text, header=header)
