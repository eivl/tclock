"""Command-line interface. Parses arguments into :class:`Options` and starts the TUI."""

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from tclock import __version__, ui
from tclock import completion as comp
from tclock.config import ConfigExistsError, config_path, load_config, write_template
from tclock.modes import Stopwatch
from tclock.parsing import ParseError, parse_color, parse_datetime, parse_duration, parse_timezone
from tclock.resolve import Options, ResolveError, resolve

app = typer.Typer(
    name="tclock",
    help="A clock, timer, stopwatch and countdown in your terminal. Press q to quit.",
    invoke_without_command=True,
    add_completion=False,  # replaced by our own options below, which add activation hints
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
config_app = typer.Typer(
    help="Manage the config file.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(config_app, name="config")


def _validate_color(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_color(value)
        except ParseError as exc:
            raise typer.BadParameter(str(exc)) from None
    return value


def _validate_durations(values: list[str] | None) -> list[str] | None:
    for value in values or []:
        try:
            parse_duration(value)
        except ParseError as exc:
            raise typer.BadParameter(str(exc)) from None
    return values


def _validate_timezone(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_timezone(value)
        except ParseError as exc:
            raise typer.BadParameter(str(exc)) from None
    return value


def _validate_datetime(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_datetime(value)
        except ParseError as exc:
            raise typer.BadParameter(str(exc)) from None
    return value


def _version(value: bool) -> None:
    if value:
        typer.echo(f"tclock {__version__}")
        raise typer.Exit()


def _shell_or_exit(shell: str | None) -> str:
    if shell is not None:
        return shell
    try:
        return comp.detect_shell()
    except comp.ShellError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from None


def _install_completion(value: bool) -> None:
    if not value:
        return
    shell = _shell_or_exit(None)
    path = comp.install_completion(shell)
    typer.echo(f"{shell} completion installed in {path}")
    typer.echo("Completion will take effect once you restart the terminal.")
    activate = comp.activate_command(shell, path)
    if activate is None:
        typer.echo(f"{shell} loads it on first use, so no restart is needed.")
    else:
        typer.echo("To use it in this shell right away, run:")
        typer.echo(f"  {activate}")
    raise typer.Exit()


def _show_completion(value: bool) -> None:
    if not value:
        return
    typer.echo(comp.script(_shell_or_exit(None)))
    raise typer.Exit()


def _options(ctx: typer.Context) -> Options:
    options = ctx.find_root().obj
    assert isinstance(options, Options)
    return options


@app.callback()
def root(
    ctx: typer.Context,
    color: Annotated[
        str | None,
        typer.Option(
            "--color",
            "-c",
            callback=_validate_color,
            help="Digit color: black, red, green, yellow, blue, magenta, cyan, gray, darkgray, "
            "lightred, lightgreen, lightyellow, lightblue, lightmagenta, lightcyan, white, "
            "or #rrggbb.",
        ),
    ] = None,
    size: Annotated[
        int | None, typer.Option("--size", "-s", min=1, help="Digit size, a positive integer.")
    ] = None,
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
    install_completion: Annotated[
        bool,
        typer.Option(
            "--install-completion",
            callback=_install_completion,
            is_eager=True,
            help="Install completion for the current shell.",
        ),
    ] = False,
    show_completion: Annotated[
        bool,
        typer.Option(
            "--show-completion",
            callback=_show_completion,
            is_eager=True,
            help="Show the completion script for the current shell.",
        ),
    ] = False,
) -> None:
    ctx.obj = Options(color=color, size=size)
    if ctx.invoked_subcommand is None:
        _launch(ctx.obj)


@app.command()
def clock(
    ctx: typer.Context,
    timezone: Annotated[
        str | None,
        typer.Option(
            "--timezone", "-z", callback=_validate_timezone, help='IANA zone, e.g. "Europe/Oslo".'
        ),
    ] = None,
    no_date: Annotated[bool, typer.Option("--no-date", "-D", help="Hide the date.")] = False,
    no_seconds: Annotated[bool, typer.Option("--no-seconds", "-S", help="Hide seconds.")] = False,
    millis: Annotated[
        bool, typer.Option("--millis", "-m", help="Show tenths of a second.")
    ] = False,
) -> None:
    """Show the current time (the default mode)."""
    options = _options(ctx)
    options.mode = "clock"
    options.timezone = timezone
    options.no_date = no_date
    options.no_seconds = no_seconds
    options.millis = millis
    _launch(options)


@app.command()
def timer(
    ctx: typer.Context,
    durations: Annotated[
        list[str] | None,
        typer.Option(
            "--duration",
            "-d",
            callback=_validate_durations,
            help="Duration like 30s, 5m, 1h, 2d. Repeat the flag to run several in sequence.",
        ),
    ] = None,
    titles: Annotated[
        list[str] | None,
        typer.Option("--title", "-t", help="Title per duration. Repeat the flag for several."),
    ] = None,
    repeat: Annotated[bool, typer.Option("--repeat", "-r", help="Restart when finished.")] = False,
    no_millis: Annotated[bool, typer.Option("--no-millis", "-M", help="Hide tenths.")] = False,
    paused: Annotated[bool, typer.Option("--paused", "-P", help="Start paused.")] = False,
    auto_quit: Annotated[bool, typer.Option("--quit", "-Q", help="Exit when time is up.")] = False,
    execute: Annotated[
        str | None,
        typer.Option("--execute", "-e", help="Shell command to run when time is up."),
    ] = None,
) -> None:
    """Count down one or more durations. Space pauses and resumes."""
    options = _options(ctx)
    options.mode = "timer"
    options.durations = durations or []
    options.titles = titles or []
    options.repeat = repeat
    options.no_millis = no_millis
    options.paused = paused
    options.auto_quit = auto_quit
    options.execute = execute
    _launch(options)


@app.command()
def stopwatch(ctx: typer.Context) -> None:
    """Count up from zero. Space pauses and resumes; the time is printed on exit."""
    options = _options(ctx)
    options.mode = "stopwatch"
    _launch(options)


@app.command()
def countdown(
    ctx: typer.Context,
    time: Annotated[
        str | None,
        typer.Option(
            "--time",
            "-t",
            callback=_validate_datetime,
            help='Target: "2027-01-01", "20:00", "2026-12-25 20:00:00" or RFC 3339.',
        ),
    ] = None,
    title: Annotated[str | None, typer.Option("--title", "-T", help="Header text.")] = None,
    continue_on_zero: Annotated[
        bool, typer.Option("--continue", "-c", help="Keep counting past the target.")
    ] = False,
    reverse: Annotated[
        bool, typer.Option("--reverse", "-r", help="Count up since the target instead.")
    ] = False,
    millis: Annotated[
        bool, typer.Option("--millis", "-m", help="Show tenths of a second.")
    ] = False,
) -> None:
    """Show the time until (or since) a specific moment."""
    options = _options(ctx)
    options.mode = "countdown"
    options.time = time
    options.title = title
    options.continue_on_zero = continue_on_zero
    options.reverse = reverse
    options.millis = millis
    _launch(options)


@config_app.command("init")
def config_init(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path", "-p", dir_okay=False, help="Write here instead of the platform location."
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite an existing file.")
    ] = False,
) -> None:
    """Create a config file with every option listed at its default, commented out."""
    try:
        written = write_template(path, force=force)
    except ConfigExistsError as exc:
        typer.echo(f"Error: {exc} already exists. Use --force to overwrite it.", err=True)
        raise typer.Exit(code=1) from None
    except OSError as exc:
        typer.echo(f"Error: could not write config file: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Wrote {written}")


@config_app.command("path")
def config_path_command() -> None:
    """Print where the config file is read from on this platform."""
    typer.echo(str(config_path()))


class Shell(str, Enum):
    """Shells with completion support."""

    bash = "bash"
    zsh = "zsh"
    fish = "fish"
    powershell = "powershell"
    pwsh = "pwsh"


@app.command()
def completion(
    shell: Annotated[
        Shell | None,
        typer.Option(
            "--shell",
            show_default=False,
            help="Shell to check. Detected from the environment if omitted.",
        ),
    ] = None,
    print_script: Annotated[
        bool, typer.Option("--script", help="Print the completion script instead.")
    ] = False,
) -> None:
    """Check whether shell completion is installed and active. Exit code 1 if not installed."""
    name = _shell_or_exit(shell.value if shell is not None else None)
    if print_script:
        typer.echo(comp.script(name))
        return
    st = comp.status(name)
    detected = " (detected)" if shell is None else ""
    typer.echo(f"Shell: {name}{detected}")
    if st.script_path is None:
        for note in st.notes:
            typer.echo(f"Note: {note}")
        typer.echo(f"Completion for {name} could not be checked.")
        raise typer.Exit(code=1)
    if not st.script_exists:
        script_state = "missing"
    elif not st.script_current:
        script_state = "outdated, reinstall to update"
    else:
        script_state = "ok"
    typer.echo(f"Script: {st.script_path}  [{script_state}]")
    if st.rc_path is not None:
        rc_state = "loads it" if st.rc_wired else "does not load it"
        typer.echo(f"Startup file: {st.rc_path}  [{rc_state}]")
    if not st.installed:
        typer.echo("Run `tclock --install-completion` to install it.")
        raise typer.Exit(code=1)
    if st.active is None:
        typer.echo(f"Completion for {name} is installed; {name} loads it on first use.")
        return
    if not st.hook_present:
        typer.echo(
            f"Completion for {name} is installed, but it predates the {comp.ENV_VAR} hook, so"
            " whether this shell has loaded it cannot be checked."
        )
        typer.echo("Run `tclock --install-completion` again to add the hook.")
        return
    if st.active:
        typer.echo(f"Completion for {name} is installed and active in this shell.")
        return
    typer.echo(f"Completion for {name} is installed but not active in this shell yet.")
    typer.echo("It was probably installed after this shell started. To use it now, run:")
    typer.echo(f"  {comp.activate_command(name, st.script_path)}")


def _launch(options: Options) -> None:
    config = load_config()
    try:
        resolved = resolve(options, config)
    except ResolveError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from None
    final = ui.run(resolved.engine, color=resolved.color, size=resolved.size, config=config)
    if isinstance(final, Stopwatch):
        typer.echo(f"Stopwatch time: {final.display_time()}")


def main() -> None:
    app()
