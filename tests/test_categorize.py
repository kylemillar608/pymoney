"""Tests for categorization rules engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from pymoney.categorize.rules import apply_rules, categorize_uncategorized
from pymoney.db import get_in_memory_connection


_TEST_CATEGORIES_YAML = """
categories:
  - name: Groceries
    group: Food & Dining
    rules:
      - contains: ["TRADER JOE", "WHOLE FOODS"]
      - regex: "GROCERY|MARKET"
  - name: Restaurants
    group: Food & Dining
    rules:
      - contains: ["STARBUCKS", "DOORDASH"]
  - name: Paycheck
    group: Income
    is_income: true
    rules:
      - regex: "PAYROLL|DIRECT DEPOSIT"
"""


def _write_test_config() -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(_TEST_CATEGORIES_YAML)
    f.close()
    return Path(f.name)


def test_contains_match():
    cfg = _write_test_config()
    result = apply_rules("TRADER JOE'S #123", config_path=cfg)
    assert result == "Groceries"


def test_contains_match_full_description():
    cfg = _write_test_config()
    result = apply_rules("STORE", "WHOLE FOODS MARKET", config_path=cfg)
    assert result == "Groceries"


def test_regex_match():
    cfg = _write_test_config()
    result = apply_rules("SAFEWAY GROCERY STORE", config_path=cfg)
    assert result == "Groceries"


def test_no_match():
    cfg = _write_test_config()
    result = apply_rules("SOME UNKNOWN MERCHANT", config_path=cfg)
    assert result is None


def test_skip_manually_overridden():
    """Transactions with manually_overridden=TRUE should not be categorized."""
    conn = get_in_memory_connection()

    conn.execute("""
        INSERT INTO transactions
            (id, date, description, amount, account, manually_overridden)
        VALUES
            ('tx-1', '2024-03-01', 'TRADER JOE''S', -45.00, 'Chase', TRUE),
            ('tx-2', '2024-03-01', 'TRADER JOE''S', -30.00, 'Chase', FALSE)
    """)

    cfg = _write_test_config()

    # Patch get_connection to return our in-memory conn
    from unittest.mock import patch
    with patch("pymoney.categorize.rules.get_connection", return_value=conn):
        count = categorize_uncategorized(config_path=cfg)

    assert count == 1

    rows = conn.execute(
        "SELECT id, category FROM transactions ORDER BY id"
    ).fetchall()
    assert rows[0][1] is None  # tx-1 unchanged (manually_overridden)
    assert rows[1][1] == "Groceries"  # tx-2 categorized


def test_categorize_uncategorized_skips_already_categorized():
    """Transactions that already have a category should not be touched."""
    conn = get_in_memory_connection()

    conn.execute("""
        INSERT INTO transactions
            (id, date, description, amount, account, category, manually_overridden)
        VALUES ('tx-1', '2024-03-01', 'TRADER JOE''S', -45.00, 'Chase', 'CustomCat', FALSE)
    """)

    cfg = _write_test_config()
    from unittest.mock import patch
    with patch("pymoney.categorize.rules.get_connection", return_value=conn):
        count = categorize_uncategorized(config_path=cfg)

    assert count == 0
    row = conn.execute("SELECT category FROM transactions WHERE id = 'tx-1'").fetchone()
    assert row[0] == "CustomCat"
