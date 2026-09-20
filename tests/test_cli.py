from pathlib import Path

import pytest
from typer.testing import CliRunner

from tclock import __version__, cli, config
from tclock.config import render_template
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


# --- config subcommands ----------------------------------------------------------------------


def test_config_without_subcommand_shows_help() -> None:
    result = runner.invoke(cli.app, ["config"])
    assert "Usage" in result.output
    assert "init" in result.output and "path" in result.output


def test_config_path_prints_platform_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "config_path", lambda: tmp_path / "config.toml")
    result = runner.invoke(cli.app, ["config", "path"])
    assert result.exit_code == 0
    assert result.output.strip() == str(tmp_path / "config.toml")


def test_config_init_writes_template_to_explicit_path(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    result = runner.invoke(cli.app, ["config", "init", "--path", str(path)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"Wrote {path}"
    assert path.read_text(encoding="utf-8") == render_template(path)


def test_config_init_uses_platform_path_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "tclock" / "config.toml"
    monkeypatch.setattr(config, "config_path", lambda: target)
    result = runner.invoke(cli.app, ["config", "init"])
    assert result.exit_code == 0, result.output
    assert target.is_file()


def test_config_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("keep = 1\n", encoding="utf-8")
    result = runner.invoke(cli.app, ["config", "init", "--path", str(path)])
    assert result.exit_code == 1
    assert "already exists" in result.output and "--force" in result.output
    assert path.read_text(encoding="utf-8") == "keep = 1\n"
    result = runner.invoke(cli.app, ["config", "init", "--path", str(path), "--force"])
    assert result.exit_code == 0, result.output
    assert path.read_text(encoding="utf-8") == render_template(path)


def test_config_init_reports_unwritable_location(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    result = runner.invoke(cli.app, ["config", "init", "--path", str(blocker / "config.toml")])
    assert result.exit_code == 1
    assert "could not write config file" in result.output


def test_config_init_does_not_launch_the_ui(launched: list[Options], tmp_path: Path) -> None:
    runner.invoke(cli.app, ["config", "init", "--path", str(tmp_path / "c.toml")])
    assert launched == []


# --- shell completion ------------------------------------------------------------------------

SHELLS = ["bash", "zsh", "fish", "powershell", "pwsh"]


@pytest.mark.parametrize("shell", SHELLS)
def test_completion_prints_script_for_each_shell(shell: str) -> None:
    result = runner.invoke(cli.app, ["completion", shell])
    assert result.exit_code == 0, result.output
    assert "_TCLOCK_COMPLETE" in result.output
    assert "tclock" in result.output


@pytest.mark.parametrize(
    ("shell", "opening"),
    [
        ("bash", "_tclock_completion() {"),
        ("zsh", "#compdef tclock"),
        ("fish", "complete --command tclock"),
        ("powershell", "Import-Module PSReadLine"),
        ("pwsh", "Import-Module PSReadLine"),
    ],
)
def test_completion_script_has_the_shape_each_shell_expects(shell: str, opening: str) -> None:
    result = runner.invoke(cli.app, ["completion", shell])
    assert result.output.startswith(opening)


def test_completion_rejects_unknown_shell() -> None:
    result = runner.invoke(cli.app, ["completion", "elvish"])
    assert result.exit_code == 2
    assert "elvish" in result.output


def test_completion_detects_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shellingham, "detect_shell", lambda: ("fish", "/usr/bin/fish"))
    result = runner.invoke(cli.app, ["completion"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("complete --command tclock")


def test_completion_reports_undetectable_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> tuple[str, str]:
        raise cli.shellingham.ShellDetectionFailure()

    monkeypatch.setattr(cli.shellingham, "detect_shell", fail)
    result = runner.invoke(cli.app, ["completion"])
    assert result.exit_code == 2
    assert "could not detect the shell" in result.output


def test_completion_reports_unsupported_detected_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shellingham, "detect_shell", lambda: ("elvish", "/usr/bin/elvish"))
    result = runner.invoke(cli.app, ["completion"])
    assert result.exit_code == 2
    assert "elvish has no completion support" in result.output


def _complete(words: str) -> list[str]:
    """Drive the protocol the bash script uses and return the candidates, one per line."""
    cword = len(words.split()) - 1  # index of the word being completed
    env = {"_TCLOCK_COMPLETE": "complete_bash", "COMP_WORDS": words, "COMP_CWORD": str(cword)}
    result = runner.invoke(cli.app, [], env=env)
    assert result.exit_code == 0, result.output
    return result.output.split()


def test_completion_protocol_completes_subcommands() -> None:
    assert _complete("tclock ti") == ["timer"]
    assert set(_complete("tclock c")) == {"clock", "countdown", "config", "completion"}


def test_completion_protocol_completes_options_and_nested_commands() -> None:
    assert _complete("tclock timer --du") == ["--duration"]
    assert _complete("tclock config i") == ["init"]
    assert _complete("tclock completion po") == ["powershell"]
