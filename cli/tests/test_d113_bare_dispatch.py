"""D113: bare `octopus` launches the app — TUI on TTY, list otherwise.

The callback re-dispatches through Click's built command tree, so we assert
on the isatty branch by patching the two leaf commands' underlying functions
where Click actually calls them: swap the built subcommand's `.invoke`.
"""
import typer
from typer.testing import CliRunner
from octopus import cli

runner = CliRunner()


def _patch_leaves(monkeypatch, sink):
    """Patch the .invoke of the tui/list commands on the *live* app tree."""
    group = typer.main.get_command(cli.app)
    # cli.app caches its built group; get_command returns that same cached
    # TyperGroup, so patches here hit the object the callback will look up.
    monkeypatch.setattr(group.commands["tui"], "invoke",
                        lambda ctx: sink.append("tui"), raising=True)
    monkeypatch.setattr(group.commands["list"], "invoke",
                        lambda ctx: sink.append("list"), raising=True)
    return group


def test_bare_non_tty_dispatches_to_list(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    sink = []
    group = _patch_leaves(monkeypatch, sink)
    group.main([], standalone_mode=False)
    assert sink == ["list"]


def test_bare_tty_dispatches_to_tui(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    sink = []
    group = _patch_leaves(monkeypatch, sink)
    group.main([], standalone_mode=False)
    assert sink == ["tui"]


def test_help_still_shows_menu():
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0 and "Commands" in result.output


def test_version_still_works():
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0 and "octopus" in result.output
