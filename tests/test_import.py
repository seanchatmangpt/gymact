"""Test gymact."""

import gymact


def test_import() -> None:
    """Test that the package can be imported."""
    assert isinstance(gymact.__name__, str)
