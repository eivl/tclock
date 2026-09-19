"""Textual front end: one app, one big-digit widget, header and footer labels."""

import subprocess
from collections.abc import Callable

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import Label

from tclock import font
from tclock.config import Config
from tclock.modes import Mode, Pausable, Timer
from tclock.resolve import Options, build_clock, build_stopwatch, build_timer

FLASH_CLASS = "-flash"
FLASH_TEXT_COLOR = "ansi_black"


def run_shell(command: str) -> str:
    """Run ``command`` in the platform shell and summarise the outcome on one line."""
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, errors="replace")
    except OSError as exc:
        return f"[FAILED] {exc}"
    if proc.returncode != 0:
        return " ".join(f"[ERROR] {proc.stderr}".split())
    return " ".join(f"[SUCCEED] {proc.stdout}".split())


class BigTime(Widget):
    """Draws text in the bricks font, centred horizontally."""

    DEFAULT_CSS = """
    BigTime {
        width: 100%;
        height: auto;
        content-align-horizontal: center;
    }
    """

    def __init__(self, size: int = 1, *, id: str | None = None) -> None:
        super().__init__(id=id)
        # Not ``self.size``: Textual's Widget.size is a read-only property.
        self.scale = size
        self.rows: list[str] = font.render("", size)

    def set_text(self, text: str | None) -> None:
        rows = font.render(text or "", self.scale)
        if rows != self.rows:
            self.rows = rows
            self.refresh(layout=True)

    def render(self) -> Text:
        return Text("\n".join(self.rows), no_wrap=True, end="")

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return len(self.rows)


class ClockApp(App[None]):
    CSS_PATH = "app.tcss"
    TICK_SECONDS = 0.1
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_pause", "Pause/resume", show=False),
        Binding("c", "mode_clock", "Clock", show=False),
        Binding("w", "mode_stopwatch", "Stopwatch", show=False),
        Binding("t", "mode_timer", "Timer", show=False),
    ]

    def __init__(
        self,
        engine: Mode,
        *,
        color: str,
        size: int,
        config: Config,
        runner: Callable[[str], str] = run_shell,
    ) -> None:
        super().__init__()
        self.engine = engine
        # Not ``self.size``/``self.color``: App.size is a read-only Textual property.
        self.digit_color = color
        self.digit_size = size
        self.config = config
        self._runner = runner
        self._execute_running = False

    def compose(self) -> ComposeResult:
        with Vertical(id="body"):
            yield Label("", id="header")
            yield BigTime(self.digit_size, id="time")
            yield Label("", id="footer")

    def on_mount(self) -> None:
        self.tick()
        self.set_interval(self.TICK_SECONDS, self.tick)

    def tick(self) -> None:
        frame = self.engine.snapshot()
        self.query_one("#header", Label).update(frame.header or "")
        self.query_one("#footer", Label).update(frame.footer or "")
        big = self.query_one(BigTime)
        big.set_text(frame.text)
        big.styles.color = FLASH_TEXT_COLOR if frame.flash else self.digit_color
        self.screen.set_class(frame.flash, FLASH_CLASS)
        self._maybe_execute()
        if frame.finished:
            self.exit()

    def _maybe_execute(self) -> None:
        engine = self.engine
        if not isinstance(engine, Timer) or not engine.execute_pending or self._execute_running:
            return
        if engine.execute is None:
            return
        self._execute_running = True
        self._run_execute(engine, engine.execute)

    @work(thread=True, exclusive=True)
    def _run_execute(self, timer: Timer, command: str) -> None:
        result = self._runner(command)
        self.call_from_thread(self._on_execute_done, timer, result)

    def _on_execute_done(self, timer: Timer, result: str) -> None:
        timer.set_execute_result(result)
        self._execute_running = False
        if timer is self.engine:
            self.tick()

    def action_toggle_pause(self) -> None:
        if isinstance(self.engine, Pausable):
            self.engine.toggle_paused()
            self.tick()

    def action_mode_clock(self) -> None:
        self._switch(build_clock(Options(), self.config))

    def action_mode_stopwatch(self) -> None:
        self._switch(build_stopwatch())

    def action_mode_timer(self) -> None:
        self._switch(build_timer(Options(), self.config))

    def _switch(self, engine: Mode) -> None:
        self.engine = engine
        self._execute_running = False
        self.tick()


def run(engine: Mode, *, color: str, size: int, config: Config) -> Mode:
    """Run the TUI until the user quits; return the engine that was active at exit."""
    app = ClockApp(engine, color=color, size=size, config=config)
    app.run()
    return app.engine
