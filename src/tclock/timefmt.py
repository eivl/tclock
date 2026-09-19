"""Formatting of millisecond durations as D:HH:MM:SS[.d] strings."""

from enum import Enum


class DurationFormat(Enum):
    """How much precision a formatted duration shows."""

    HOUR_MIN_SEC = "hms"
    HOUR_MIN_SEC_DECI = "hmsd"


def format_duration(ms: int, fmt: DurationFormat) -> str:
    """Format ``ms`` like ``1:05``, ``1:30:00``, ``2:01:00:00`` or ``0:05.3``.

    Minutes and seconds are always present. Hours appear once the duration reaches one
    hour, days once it reaches 24 hours. The leading component is not zero-padded, the
    rest are. Negative durations get a leading ``-``.
    """
    negative = ms < 0
    ms = abs(ms)
    total_seconds, millis = divmod(ms, 1000)
    total_minutes, seconds = divmod(total_seconds, 60)
    total_hours, minutes = divmod(total_minutes, 60)
    days, hours = divmod(total_hours, 24)

    parts: list[str] = []
    if days > 0:
        parts.append(str(days))
    if total_hours > 0:
        parts.append(f"{hours:02d}" if parts else str(hours))
    parts.append(f"{minutes:02d}" if parts else str(minutes))
    parts.append(f"{seconds:02d}")
    result = ":".join(parts)
    if fmt is DurationFormat.HOUR_MIN_SEC_DECI:
        result += f".{millis // 100}"
    return f"-{result}" if negative else result
