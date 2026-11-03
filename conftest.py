"""Shared fixtures for the tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmjudge.data import load_items

ITEMS_PATH = Path(__file__).resolve().parent / "data" / "items.json"


@pytest.fixture()
def items():
    """The measured item file, used by tests and by the audit itself."""

    return load_items(ITEMS_PATH)
