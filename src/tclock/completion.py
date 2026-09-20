"""Shell completion: script generation, installation, activation hints and a status check.

Typer generates the scripts and does the installing. This module wraps that with the
paths Typer uses, so ``tclock completion`` can tell whether an install is in place and
``--install-completion`` can say how to activate it without restarting the shell.
"""

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import shellingham

# Typer has no public API for these; the tests pin the behaviour we rely on.
from typer._completion_classes import completion_init
from typer._completion_shared import get_completion_script, install

PROG_NAME = "tclock"
COMPLETE_VAR = "_TCLOCK_COMPLETE"
SHELLS = ("bash", "zsh", "fish", "powershell", "pwsh")

# Exported by the startup hook so a child tclock can tell whether the shell it was started
# from has loaded completion. The value is the shell name, so a bash started from a zsh does
# not count zsh's variable as its own. fish loads completions lazily and needs no hook.
ENV_VAR = "TCLOCK_COMPLETION"

# Registers Typer's completion classes with Click so the _TCLOCK_COMPLETE protocol works
# even though the app does not use Typer's own --install-completion option.
completion_init()


class ShellError(Exception):
    """The shell could not be detected, or has no completion support."""


def detect_shell() -> str:
    """Name of the shell running us, via shellingham."""
    try:
        name, _ = shellingham.detect_shell()
    except shellingham.ShellDetectionFailure:
        raise ShellError("could not detect the shell; pass one of " + ", ".join(SHELLS)) from None
    if name not in SHELLS:
        raise ShellError(f"{name} has no completion support; pass one of " + ", ".join(SHELLS))
    return str(name)  # shellingham is untyped


def _check(shell: str) -> str:
    if shell not in SHELLS:
        raise ShellError(f"{shell} has no completion support; pass one of " + ", ".join(SHELLS))
    return shell


def hook_line(shell: str) -> str | None:
    """The line that marks this shell as having loaded completion, or ``None`` for fish."""
    if shell == "bash":
        return f"export {ENV_VAR}=bash"
    if shell == "zsh":
        return f"export {ENV_VAR}=zsh"
    if shell in {"powershell", "pwsh"}:
        return f'$env:{ENV_VAR} = "{shell}"'
    return None


def script(shell: str) -> str:
    """The completion script for ``shell``.

    For bash and PowerShell the script itself is what the startup file loads, so the hook
    line is part of it. zsh's script is a compdef file that is not sourced at startup, so its
    hook goes in ``.zshrc`` at install time instead.
    """
    text = get_completion_script(
        prog_name=PROG_NAME, complete_var=COMPLETE_VAR, shell=_check(shell)
    )
    if shell in {"bash", "powershell", "pwsh"}:
        text = f"{text.rstrip()}\n{hook_line(shell)}\n"
    return text


def install_completion(shell: str) -> Path:
    """Install completion for ``shell`` the way Typer does, plus the hook, and return the path."""
    _, path = install(shell=_check(shell), prog_name=PROG_NAME, complete_var=COMPLETE_VAR)
    if shell == "bash":
        path.write_text(script(shell), encoding="utf-8")  # Typer's script plus the hook
    elif shell == "zsh":
        _append_line(Path.home() / ".zshrc", hook_line(shell))
    elif shell in {"powershell", "pwsh"}:
        _append_line(path, hook_line(shell))  # Typer appended its script; add the hook after it
    return path


def _append_line(path: Path, line: str | None) -> None:
    if line is None:
        return
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    if line in content:
        return
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(f"{content}{line}\n", encoding="utf-8")


def active_in_this_shell(shell: str, environ: Mapping[str, str] | None = None) -> bool | None:
    """Whether the shell that started us has run the hook. ``None`` for fish (no hook)."""
    if hook_line(shell) is None:
        return None
    environ = environ if environ is not None else os.environ
    return environ.get(ENV_VAR) == shell


def activate_command(shell: str, path: Path) -> str | None:
    """Command that loads a freshly installed script into the running shell.

    ``None`` means no action is needed: fish loads completions on first use.
    """
    if shell == "bash":
        return f"source '{path}'"
    if shell == "zsh":
        # Typer's ~/.zshrc line plus our hook, so the status check turns green right away.
        return f"fpath+=~/.zfunc; autoload -Uz compinit; compinit; {hook_line(shell)}"
    if shell in {"powershell", "pwsh"}:
        return ". $PROFILE"
    return None


@dataclass
class Status:
    shell: str
    script_path: Path | None
    script_exists: bool = False
    script_current: bool = False
    rc_path: Path | None = None
    rc_wired: bool = True
    hook_present: bool = True
    active: bool | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def installed(self) -> bool:
        return self.script_exists and self.script_current and self.rc_wired


def powershell_profile(shell: str) -> Path | None:
    """Path of the PowerShell profile, or ``None`` if the shell cannot be run."""
    try:
        result = subprocess.run(
            [shell, "-NoProfile", "-Command", "echo", "$profile"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip())


def status(
    shell: str, home: Path | None = None, environ: Mapping[str, str] | None = None
) -> Status:
    """Whether completion for ``shell`` is installed at the paths Typer uses, and active."""
    home = home if home is not None else Path.home()
    expected = script(_check(shell)).strip()
    if shell == "bash":
        result = Status(shell, home / ".bash_completions" / f"{PROG_NAME}.sh")
        result.rc_path = home / ".bashrc"
        result.rc_wired = _file_contains(result.rc_path, f"source '{result.script_path}'")
    elif shell == "zsh":
        result = Status(shell, home / ".zfunc" / f"_{PROG_NAME}")
        result.rc_path = home / ".zshrc"
        result.rc_wired = _file_contains(result.rc_path, ".zfunc")
        result.hook_present = _file_contains(result.rc_path, hook_line(shell) or "")
    elif shell == "fish":
        result = Status(shell, home / ".config" / "fish" / "completions" / f"{PROG_NAME}.fish")
    elif shell in {"powershell", "pwsh"}:
        profile = powershell_profile(shell)
        result = Status(shell, profile)
        if profile is None:
            result.notes.append(f"could not run {shell} to find its profile")
            return result
        # Typer appends the script to the profile rather than writing a separate file.
        result.script_exists = _file_contains(profile, COMPLETE_VAR)
        result.script_current = _file_contains(profile, expected)
        result.hook_present = result.script_current
        result.active = active_in_this_shell(shell, environ)
        return result
    else:  # pragma: no cover - _check above rejects anything else
        raise AssertionError(shell)
    assert result.script_path is not None
    result.script_exists = result.script_path.is_file()
    if result.script_exists:
        current = result.script_path.read_text(encoding="utf-8").strip()
        result.script_current = current == expected
    if shell == "bash":
        result.hook_present = result.script_current  # the hook is part of the script
    result.active = active_in_this_shell(shell, environ)
    return result


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False
