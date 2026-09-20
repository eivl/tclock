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
    assert comp.activate_command("bash", path) == f"source '{path}'"
    assert comp.activate_command("zsh", path) == (
        "fpath+=~/.zfunc; autoload -Uz compinit; compinit; export TCLOCK_COMPLETION=zsh"
    )
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


# --- hook and active check -------------------------------------------------------------------


def test_hook_line_per_shell() -> None:
    assert comp.hook_line("bash") == "export TCLOCK_COMPLETION=bash"
    assert comp.hook_line("zsh") == "export TCLOCK_COMPLETION=zsh"
    assert comp.hook_line("powershell") == '$env:TCLOCK_COMPLETION = "powershell"'
    assert comp.hook_line("pwsh") == '$env:TCLOCK_COMPLETION = "pwsh"'
    assert comp.hook_line("fish") is None


def test_scripts_embed_the_hook_where_the_script_is_sourced_at_startup() -> None:
    assert comp.script("bash").endswith("export TCLOCK_COMPLETION=bash\n")
    assert comp.script("pwsh").endswith('$env:TCLOCK_COMPLETION = "pwsh"\n')
    assert "TCLOCK_COMPLETION" not in comp.script("zsh")
    assert "TCLOCK_COMPLETION" not in comp.script("fish")


def test_install_zsh_adds_hook_to_zshrc_once(home: Path) -> None:
    comp.install_completion("zsh")
    comp.install_completion("zsh")
    zshrc = (home / ".zshrc").read_text(encoding="utf-8")
    assert zshrc.count("export TCLOCK_COMPLETION=zsh") == 1
    assert "fpath+=~/.zfunc" in zshrc
    assert "TCLOCK_COMPLETION" not in (home / ".zfunc" / "_tclock").read_text(encoding="utf-8")


def test_install_bash_script_contains_hook(home: Path) -> None:
    path = comp.install_completion("bash")
    assert path.read_text(encoding="utf-8") == comp.script("bash")
    assert comp.status("bash", home).hook_present


def test_active_in_this_shell_matches_shell_name() -> None:
    assert comp.active_in_this_shell("zsh", {"TCLOCK_COMPLETION": "zsh"}) is True
    assert comp.active_in_this_shell("bash", {"TCLOCK_COMPLETION": "zsh"}) is False
    assert comp.active_in_this_shell("zsh", {}) is False
    assert comp.active_in_this_shell("fish", {"TCLOCK_COMPLETION": "fish"}) is None


def test_active_reads_os_environ_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TCLOCK_COMPLETION", "bash")
    assert comp.active_in_this_shell("bash") is True
    monkeypatch.delenv("TCLOCK_COMPLETION")
    assert comp.active_in_this_shell("bash") is False


def test_status_reports_active_and_hook(home: Path) -> None:
    comp.install_completion("zsh")
    st = comp.status("zsh", home, {"TCLOCK_COMPLETION": "zsh"})
    assert st.installed and st.hook_present and st.active is True
    st = comp.status("zsh", home, {})
    assert st.installed and st.hook_present and st.active is False


def test_status_zsh_install_predating_hook(home: Path) -> None:
    comp.install_completion("zsh")
    zshrc = home / ".zshrc"
    zshrc.write_text(
        zshrc.read_text(encoding="utf-8").replace("export TCLOCK_COMPLETION=zsh\n", ""),
        encoding="utf-8",
    )
    st = comp.status("zsh", home, {})
    assert st.installed and not st.hook_present


def test_status_fish_has_no_active_notion(home: Path) -> None:
    comp.install_completion("fish")
    st = comp.status("fish", home, {"TCLOCK_COMPLETION": "fish"})
    assert st.installed and st.hook_present and st.active is None


def test_status_powershell_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    profile = tmp_path / "profile.ps1"
    monkeypatch.setattr(comp, "powershell_profile", lambda shell: profile)
    profile.write_text(comp.script("pwsh"), encoding="utf-8")
    st = comp.status("pwsh", environ={"TCLOCK_COMPLETION": "pwsh"})
    assert st.installed and st.hook_present and st.active is True
