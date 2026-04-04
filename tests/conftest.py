"""Shared fixtures for pymoney tests."""

import pytest

from pymoney.db import get_in_memory_connection


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema initialized."""
    return get_in_memory_connection()
