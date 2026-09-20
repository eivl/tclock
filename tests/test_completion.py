from pathlib import Path

import pytest

from tclock import completion as comp

SHELLS = list(comp.SHELLS)


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A throwaway home directory that Typer's installers also see."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.mark.parametrize("shell", SHELLS)
def test_script_mentions_program_and_protocol(shell: str) -> None:
    text = comp.script(shell)
    assert "tclock" in text
    assert comp.COMPLETE_VAR in text


def test_detect_shell_uses_shellingham(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.shellingham, "detect_shell", lambda: ("fish", "/usr/bin/fish"))
    assert comp.detect_shell() == "fish"


def test_detect_shell_errors_are_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.shellingham, "detect_shell", lambda: ("elvish", "/bin/elvish"))
    with pytest.raises(comp.ShellError, match="elvish has no completion support"):
        comp.detect_shell()

    def fail() -> tuple[str, str]:
        raise comp.shellingham.ShellDetectionFailure()

    monkeypatch.setattr(comp.shellingham, "detect_shell", fail)
    with pytest.raises(comp.ShellError, match="could not detect the shell"):
        comp.detect_shell()


def test_activate_command_per_shell() -> None:
    path = Path("/h/.bash_completions/tclock.sh")
    assert comp.activate_command("bash", path) == "source '/h/.bash_completions/tclock.sh'"
    assert comp.activate_command("zsh", path) == "fpath+=~/.zfunc; autoload -Uz compinit; compinit"
    assert comp.activate_command("powershell", path) == ". $PROFILE"
    assert comp.activate_command("pwsh", path) == ". $PROFILE"
    assert comp.activate_command("fish", path) is None


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_status_before_and_after_install(shell: str, home: Path) -> None:
    before = comp.status(shell, home)
    assert not before.script_exists and not before.installed

    path = comp.install_completion(shell)
    assert path == before.script_path
    after = comp.status(shell, home)
    assert after.script_exists and after.script_current and after.rc_wired
    assert after.installed

    path.write_text("# stale\n", encoding="utf-8")
    stale = comp.status(shell, home)
    assert stale.script_exists and not stale.script_current and not stale.installed


def test_status_zsh_notices_unwired_startup_file(home: Path) -> None:
    comp.install_completion("zsh")
    (home / ".zshrc").write_text("# nothing here\n", encoding="utf-8")
    st = comp.status("zsh", home)
    assert st.script_exists and st.script_current
    assert not st.rc_wired and not st.installed


def test_status_bash_startup_line_matches_typer(home: Path) -> None:
    comp.install_completion("bash")
    st = comp.status("bash", home)
    assert st.rc_path == home / ".bashrc"
    assert f"source '{st.script_path}'" in (home / ".bashrc").read_text(encoding="utf-8")


def test_status_fish_needs_no_startup_file(home: Path) -> None:
    st = comp.status("fish", home)
    assert st.rc_path is None and st.rc_wired
    assert st.script_path == home / ".config" / "fish" / "completions" / "tclock.fish"


def test_status_powershell_reads_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    profile = tmp_path / "profile.ps1"
    monkeypatch.setattr(comp, "powershell_profile", lambda shell: profile)
    assert not comp.status("pwsh").script_exists
    profile.write_text("# mine\n" + comp.script("pwsh") + "\n", encoding="utf-8")
    st = comp.status("pwsh")
    assert st.script_path == profile
    assert st.installed


def test_status_powershell_without_shell_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp, "powershell_profile", lambda shell: None)
    st = comp.status("powershell")
    assert st.script_path is None and not st.installed
    assert st.notes == ["could not run powershell to find its profile"]


def test_powershell_profile_handles_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp, "subprocess", _FailingSubprocess)
    assert comp.powershell_profile("pwsh") is None


class _FailingSubprocess:
    CalledProcessError = comp.subprocess.CalledProcessError

    @staticmethod
    def run(*args: object, **kwargs: object) -> None:
        raise OSError("no such binary")


def test_status_rejects_unknown_shell() -> None:
    with pytest.raises(comp.ShellError):
        comp.status("elvish", Path("/nowhere"))
