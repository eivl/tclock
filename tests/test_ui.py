import pytest
from textual.color import Color
from textual.widgets import Footer, Label

from tclock import font
from tclock.config import Config
from tclock.modes import Clock, Stopwatch, Timer
from tclock.modes.base import PAUSED_FOOTER
from tclock.ui import BigTime, ClockApp, HelpScreen, run_shell
from tests.conftest import FakeClock


def label_text(app: ClockApp, selector: str) -> str:
    return str(app.query_one(selector, Label).content)


async def test_clock_renders_digits_and_header() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        big = app.query_one(BigTime)
        assert len(big.rows) == font.GLYPH_HEIGHT
        assert font.BLOCK in big.rows[0]
        assert len(label_text(app, "#header")) == len("2026-09-19")
        assert big.region.width == 80  # full width, content centred by CSS


async def test_size_scales_widget() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=2, config=Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.query_one(BigTime).rows) == font.GLYPH_HEIGHT * 2


async def test_q_quits() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code == 0


async def test_space_toggles_pause_on_stopwatch(fake_clock: FakeClock) -> None:
    app = ClockApp(Stopwatch(now_ms=fake_clock), color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert label_text(app, "#footer") == ""
        await pilot.press("space")
        await pilot.pause()
        assert label_text(app, "#footer") == PAUSED_FOOTER
        await pilot.press("space")
        await pilot.pause()
        assert label_text(app, "#footer") == ""


async def test_space_is_ignored_for_clock() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.pause()
        assert label_text(app, "#footer") == ""


async def test_mode_switch_keys() -> None:
    config = Config()
    config.timer.titles = ["From config"]
    app = ClockApp(Clock(), color="ansi_green", size=1, config=config)
    async with app.run_test() as pilot:
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.engine, Stopwatch)
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.engine, Timer)
        assert label_text(app, "#header") == "From config"
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.engine, Clock)


async def test_timer_flash_toggles_class_and_colors(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], now_ms=fake_clock)
    app = ClockApp(timer, color="ansi_red", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.has_class("-flash")
        fake_clock.ms = 1_200  # overrun, on-phase
        app.tick()
        assert app.screen.has_class("-flash")
        assert app.query_one(BigTime).styles.color == Color.parse("ansi_black")
        fake_clock.ms = 1_700  # off-phase
        app.tick()
        assert not app.screen.has_class("-flash")
        assert app.query_one(BigTime).rows == [""] * font.GLYPH_HEIGHT
        assert app.query_one(BigTime).styles.color == Color.parse("ansi_red")


async def test_finished_timer_exits_app(fake_clock: FakeClock) -> None:
    timer = Timer([1_000], auto_quit=True, now_ms=fake_clock)
    app = ClockApp(timer, color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.pause()
        fake_clock.ms = 1_100
        await pilot.pause(0.3)
    assert not app.is_running
    assert app.return_code == 0


async def test_execute_runs_via_runner_and_shows_result(fake_clock: FakeClock) -> None:
    calls: list[str] = []

    def runner(command: str) -> str:
        calls.append(command)
        return f"[SUCCEED] ran {command}"

    timer = Timer([1_000], execute="echo hi", now_ms=fake_clock)
    app = ClockApp(timer, color="ansi_green", size=1, config=Config(), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        fake_clock.ms = 1_200
        await pilot.pause(0.5)
        assert calls == ["echo hi"]
        assert timer.execute_result == "[SUCCEED] ran echo hi"
        assert label_text(app, "#footer") == "[SUCCEED] ran echo hi"


def test_run_shell_success_and_error() -> None:
    assert run_shell("echo hello") == "[SUCCEED] hello"
    result = run_shell("exit 3")
    assert result.startswith("[ERROR]")


def test_run_shell_collapses_whitespace() -> None:
    assert run_shell("echo a   b && echo c") == "[SUCCEED] a b c"


@pytest.mark.parametrize("blank", [None, ""])
def test_bigtime_blank_text_keeps_height(blank: str | None) -> None:
    big = BigTime(2)
    big.set_text("12")
    big.set_text(blank)
    assert big.rows == [""] * (font.GLYPH_HEIGHT * 2)


def screen_text(app: ClockApp) -> list[str]:
    return [strip.text.rstrip() for strip in app.screen._compositor.render_strips()]


@pytest.mark.parametrize("size", [(20, 5), (10, 3), (40, 7)])
async def test_small_terminal_clips_instead_of_scrolling(size: tuple[int, int]) -> None:
    timer = Timer([90_000], titles=["Focus"], now_ms=FakeClock())
    app = ClockApp(timer, color="ansi_green", size=1, config=Config())
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        lines = screen_text(app)
        assert len(lines) == size[1]
        for line in lines:
            assert len(line) <= size[0]
            # Only header letters, block glyphs and spaces: no scrollbar characters.
            assert set(line) <= set("Focus █")
        # The header is on the first row and the digits start right below the gap.
        assert lines[0].strip() == "Focus"
        assert lines[2].startswith("████")  # top-left of the "1" glyph


async def test_command_palette_is_disabled() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        await pilot.press("q")


async def test_ctrl_c_quits_cleanly() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.press("ctrl+c")
        await pilot.pause()
    assert not app.is_running
    assert app.return_code == 0


async def test_key_bar_hidden_until_input_then_fades() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    app.KEY_BAR_SECONDS = 0.2
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        bar = app.query_one(Footer)
        digits_before = app.query_one(BigTime).region
        assert bar.display is False
        await pilot.press("space")  # any key, even one that does nothing in clock mode
        await pilot.pause()
        assert bar.display is True
        assert "Quit" in "".join(strip.text for strip in app.screen._compositor.render_strips())
        assert app.query_one(BigTime).region == digits_before  # digits do not jump
        await pilot.pause(0.5)
        assert bar.display is False
        await pilot.hover(BigTime)  # mouse movement counts as input too
        await pilot.pause()
        assert bar.display is True
        await pilot.press("q")


async def test_question_mark_toggles_help_overlay() -> None:
    app = ClockApp(Clock(), color="ansi_green", size=1, config=Config())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) == 2
        assert isinstance(app.screen, HelpScreen)
        text = "".join(strip.text for strip in app.screen._compositor.render_strips())
        for expected in ("Quit", "Pause", "Clock", "Stopwatch", "Timer", "Ctrl+C", "help"):
            assert expected in text, expected
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        await pilot.press("question_mark")
        await pilot.pause()
        await pilot.press("q")  # q inside help closes the help, does not quit
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert app.is_running
        await pilot.press("question_mark")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1
        await pilot.press("q")
    assert not app.is_running


async def test_clock_keeps_ticking_behind_help(fake_clock: FakeClock) -> None:
    timer = Timer([5_000], now_ms=fake_clock)
    app = ClockApp(timer, color="ansi_green", size=1, config=Config())
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        fake_clock.ms = 2_000
        app.tick()  # must not raise even though the help screen is on top
        assert app.main_screen.query_one(BigTime).rows == font.render("0:03.0")
        fake_clock.ms = 6_000  # overrun: flash applies to the main screen
        app.tick()
        assert app.main_screen.has_class("-flash")
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("q")
