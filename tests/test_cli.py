"""Test gymact CLI."""

from typer.testing import CliRunner

from gymact.cli import app

runner = CliRunner()


def test_validate_profile_conforms() -> None:
    """The real bundled profile.ttl validates cleanly via the real CLI command."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "OK" in result.stdout
