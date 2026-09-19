"""Textual front end: one app, one big-digit widget, header and footer labels."""

import subprocess
from collections.abc import Callable

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.geometry import Size
from textual.screen import ModalScreen, Screen
from textual.timer import Timer as TextualTimer
from textual.widget import Widget
from textual.widgets import Footer, Label, Static

from tclock import font
from tclock.config import Config
from tclock.modes import Mode, Pausable, Timer
from tclock.resolve import Options, build_clock, build_stopwatch, build_timer

FLASH_CLASS = "-flash"
FLASH_TEXT_COLOR = "ansi_black"

# (keys, what they do) as shown in the "?" overlay.
KEY_HELP: tuple[tuple[str, str], ...] = (
    ("q, Ctrl+C", "Quit"),
    ("Space", "Pause / resume (timer and stopwatch)"),
    ("c", "Clock"),
    ("w", "Stopwatch"),
    ("t", "Timer (durations from the config file)"),
    ("?", "Toggle this help"),
)


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
        text-wrap: nowrap;
        text-overflow: clip;
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
        # Centre by hand: when the digits are wider than the terminal this leaves them
        # left-aligned and clipped on the right, like clock-tui, instead of cutting
        # off the leading digit.
        width = self.size.width
        pad = " " * max(0, (width - font.text_width_rows(self.rows)) // 2)
        return Text("\n".join(pad + row for row in self.rows), no_wrap=True, end="")

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return len(self.rows)


class HelpScreen(ModalScreen[None]):
    """The "?" overlay listing every key."""

    BINDINGS = [
        Binding("question_mark", "dismiss", "Close help", show=False),
        Binding("escape", "dismiss", "Close help", show=False),
        Binding("q", "dismiss", "Close help", show=False),
    ]

    def compose(self) -> ComposeResult:
        width = max(len(keys) for keys, _ in KEY_HELP)
        lines = "\n".join(f"{keys:<{width}}   {what}" for keys, what in KEY_HELP)
        with Vertical(id="help") as box:
            box.border_title = "Keys"
            yield Static(lines, id="help-keys")


class ClockApp(App[None]):
    CSS_PATH = "app.tcss"
    ENABLE_COMMAND_PALETTE = False
    TICK_SECONDS = 0.1
    KEY_BAR_SECONDS = 3.0
    """How long the key bar stays visible after the last keyboard or mouse input."""
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("space", "toggle_pause", "Pause", key_display="Space"),
        Binding("c", "mode_clock", "Clock"),
        Binding("w", "mode_stopwatch", "Stopwatch"),
        Binding("t", "mode_timer", "Timer"),
        Binding("question_mark", "toggle_help", "Help", key_display="?"),
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
        self._key_bar_timer: TextualTimer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="body"):
            yield Label("", id="header")
            yield BigTime(self.digit_size, id="time")
            yield Label("", id="footer")
        yield Footer(id="keybar")

    def on_mount(self) -> None:
        # Keep references: ``self.query_one`` looks at the *active* screen, which is
        # the help overlay while it is open.
        self.main_screen: Screen[object] = self.screen
        self._header = self.main_screen.query_one("#header", Label)
        self._footer = self.main_screen.query_one("#footer", Label)
        self._big = self.main_screen.query_one(BigTime)
        self._key_bar = self.main_screen.query_one(Footer)
        self._key_bar.display = False
        self.tick()
        self.set_interval(self.TICK_SECONDS, self.tick)

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, events.InputEvent):
            self._show_key_bar()
        await super().on_event(event)

    def _show_key_bar(self) -> None:
        if self._key_bar_timer is not None:
            self._key_bar_timer.stop()
        self._key_bar.display = True
        self._key_bar_timer = self.set_timer(self.KEY_BAR_SECONDS, self._hide_key_bar)

    def _hide_key_bar(self) -> None:
        self._key_bar.display = False
        self._key_bar_timer = None

    def tick(self) -> None:
        frame = self.engine.snapshot()
        self._header.update(frame.header or "")
        self._footer.update(frame.footer or "")
        self._big.set_text(frame.text)
        self._big.styles.color = FLASH_TEXT_COLOR if frame.flash else self.digit_color
        self.main_screen.set_class(frame.flash, FLASH_CLASS)
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

    def action_toggle_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def _switch(self, engine: Mode) -> None:
        self.engine = engine
        self._execute_running = False
        self.tick()


def run(engine: Mode, *, color: str, size: int, config: Config) -> Mode:
    """Run the TUI until the user quits; return the engine that was active at exit."""
    app = ClockApp(engine, color=color, size=size, config=config)
    app.run()
    return app.engine
