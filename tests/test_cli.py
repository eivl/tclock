import pytest
from typer.testing import CliRunner

from tclock import __version__, cli
from tclock.resolve import Options

runner = CliRunner()


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch) -> list[Options]:
    calls: list[Options] = []
    monkeypatch.setattr(cli, "_launch", calls.append)
    return calls


def test_version() -> None:
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"tclock {__version__}"


@pytest.mark.parametrize(
    "args",
    [["--help"], ["clock", "--help"], ["timer", "--help"], ["stopwatch", "--help"],
     ["countdown", "--help"]],
)  # fmt: skip
def test_help_works(args: list[str]) -> None:
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_no_subcommand_launches_with_mode_none(launched: list[Options]) -> None:
    result = runner.invoke(cli.app, [])
    assert result.exit_code == 0, result.output
    assert launched == [Options()]


def test_global_options_without_subcommand(launched: list[Options]) -> None:
    result = runner.invoke(cli.app, ["-c", "Yellow", "-s", "2"])
    assert result.exit_code == 0, result.output
    assert launched == [Options(color="Yellow", size=2)]


def test_clock_flags(launched: list[Options]) -> None:
    result = runner.invoke(
        cli.app, ["-c", "#e63946", "clock", "-z", "Europe/Oslo", "-D", "-S", "-m"]
    )
    assert result.exit_code == 0, result.output
    assert launched == [
        Options(
            mode="clock",
            color="#e63946",
            timezone="Europe/Oslo",
            no_date=True,
            no_seconds=True,
            millis=True,
        )
    ]


def test_timer_flags(launched: list[Options]) -> None:
    args = ["timer", "-d", "25m", "-d", "5m", "-t", "Work", "-t", "Break", "-r", "-M", "-P", "-Q",
            "-e", "notify-send -t 5 done"]  # fmt: skip
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert launched == [
        Options(
            mode="timer",
            durations=["25m", "5m"],
            titles=["Work", "Break"],
            repeat=True,
            no_millis=True,
            paused=True,
            auto_quit=True,
            execute="notify-send -t 5 done",
        )
    ]


def test_stopwatch(launched: list[Options]) -> None:
    result = runner.invoke(cli.app, ["stopwatch"])
    assert result.exit_code == 0, result.output
    assert launched == [Options(mode="stopwatch")]


def test_countdown_flags(launched: list[Options]) -> None:
    args = ["countdown", "-t", "2027-01-01", "-T", "New year", "-c", "-r", "-m"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert launched == [
        Options(
            mode="countdown",
            time="2027-01-01",
            title="New year",
            continue_on_zero=True,
            reverse=True,
            millis=True,
        )
    ]


def test_countdown_time_may_come_from_config(launched: list[Options]) -> None:
    result = runner.invoke(cli.app, ["countdown"])
    assert result.exit_code == 0, result.output
    assert launched == [Options(mode="countdown")]


@pytest.mark.parametrize(
    "args",
    [
        ["-c", "purple"],
        ["-s", "0"],
        ["timer", "-d", "5x"],
        ["clock", "-z", "Mars/Base"],
        ["countdown", "-t", "someday"],
    ],
)
def test_invalid_values_exit_2(args: list[str], launched: list[Options]) -> None:
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 2
    assert launched == []


def test_resolve_error_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    from tclock.config import Config

    monkeypatch.setattr(cli, "load_config", Config)  # ignore the user's real config file
    result = runner.invoke(cli.app, ["countdown"])
    assert result.exit_code == 2
    assert "--time" in result.output


def test_launch_prints_stopwatch_time_after_ui(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from tclock.config import Config
    from tclock.modes import Stopwatch

    class FrozenStopwatch(Stopwatch):
        def display_time(self) -> str:
            return "0:42.0"

    monkeypatch.setattr(cli, "load_config", Config)
    monkeypatch.setattr(cli.ui, "run", lambda engine, **kwargs: FrozenStopwatch())
    cli._launch(Options(mode="stopwatch"))
    assert capsys.readouterr().out.strip() == "Stopwatch time: 0:42.0"
