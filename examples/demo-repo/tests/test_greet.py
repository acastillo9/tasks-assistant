import pytest
from demo_repo import greet


def test_greets_by_name() -> None:
    assert greet("Andrés") == "Hello, Andrés!"


def test_rejects_empty_names() -> None:
    with pytest.raises(ValueError, match="name required"):
        greet("")


def test_rejects_blank_names() -> None:
    with pytest.raises(ValueError, match="name required"):
        greet("   ")
