"""Shared test helpers."""

import pytest


class FakeClock:
    """A callable millisecond clock that only moves when told to."""

    def __init__(self, ms: int = 0) -> None:
        self.ms = ms

    def __call__(self) -> int:
        return self.ms

    def advance(self, ms: int) -> None:
        self.ms += ms


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()
