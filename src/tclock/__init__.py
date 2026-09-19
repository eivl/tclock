"""tclock: a clock, timer, stopwatch and countdown for the terminal."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tclock")
except PackageNotFoundError:  # running from a checkout that is not installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
