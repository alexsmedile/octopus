"""D112: interactive adopt-on-read. Runnable check for the TTY/non-TTY branch."""
import sys
from pathlib import Path
import octopus.cli as cli


def _prep(monkeypatch, tmp_path, *, tty, confirm):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: confirm)
    monkeypatch.chdir(tmp_path)


def test_non_tty_never_adopts(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path, tty=False, confirm=True)  # confirm ignored
    assert cli._offer_adopt_cwd(tmp_path) is None
    assert not (tmp_path / ".octopus").exists()


def test_tty_no_declines(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path, tty=True, confirm=False)
    assert cli._offer_adopt_cwd(tmp_path) is None
    assert not (tmp_path / ".octopus").exists()


def test_tty_yes_adopts(monkeypatch, tmp_path):
    _prep(monkeypatch, tmp_path, tty=True, confirm=True)
    got = cli._offer_adopt_cwd(tmp_path)
    assert got == tmp_path
    assert (tmp_path / ".octopus" / "activity.md").is_file()


def test_warn_migratable(monkeypatch, tmp_path, capsys):
    (tmp_path / "TODO.md").write_text("- [ ] x\n")
    _prep(monkeypatch, tmp_path, tty=False, confirm=False)
    cli._offer_adopt_cwd(tmp_path)
    assert "octopus-migrate" in capsys.readouterr().err
