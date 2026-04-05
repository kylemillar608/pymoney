"""Rule-based categorization engine driven by config/categories.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from pymoney.db import get_connection

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "categories.yaml"


def _load_rules(config_path: Path | None = None) -> list[dict[str, Any]]:
    """Load categories and their rules from YAML config."""
    path = config_path or _CONFIG_PATH
    with path.open() as f:
        data = yaml.safe_load(f)
    return data.get("categories", [])


def sync_categories(
    conn: "duckdb.DuckDBPyConnection",
    config_path: Path | None = None,
) -> None:
    """Upsert category metadata from YAML config into the categories DB table."""
    categories = _load_rules(config_path)
    for cat in categories:
        name = cat["name"]
        group_name = cat.get("group")
        is_income = bool(cat.get("is_income", False))
        is_transfer = bool(cat.get("is_transfer", False))
        hide_from_budget = bool(cat.get("hide_from_budget", False))
        exclude_from_reports = bool(cat.get("exclude_from_reports", False))
        conn.execute("DELETE FROM categories WHERE name = ?", [name])
        conn.execute("""
            INSERT INTO categories
                (name, group_name, is_income, is_transfer, hide_from_budget, exclude_from_reports)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [name, group_name, is_income, is_transfer, hide_from_budget, exclude_from_reports])


def apply_rules(
    description: str,
    full_description: str | None = None,
    config_path: Path | None = None,
) -> str | None:
    """
    Apply categorization rules to a transaction description.

    Returns the matched category name, or None if no rule matches.
    """
    categories = _load_rules(config_path)
    text = description.upper()
    full_text = (full_description or "").upper()

    for category in categories:
        name: str = category["name"]
        for rule in category.get("rules", []):
            if "contains" in rule:
                for keyword in rule["contains"]:
                    if keyword.upper() in text or keyword.upper() in full_text:
                        return name
            if "regex" in rule:
                pattern = rule["regex"]
                if re.search(pattern, text) or re.search(pattern, full_text):
                    return name
    return None


def categorize_uncategorized(
    db_path: str | None = None,
    config_path: Path | None = None,
) -> int:
    """
    Apply rules to all transactions with NULL or empty category,
    skipping rows where manually_overridden is TRUE.

    Returns the count of transactions that were categorized.
    """
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT id, description, full_description
        FROM transactions
        WHERE (category IS NULL OR category = '')
          AND (manually_overridden IS NULL OR manually_overridden = FALSE)
    """).fetchall()

    updated = 0
    for row_id, desc, full_desc in rows:
        category = apply_rules(desc, full_desc, config_path=config_path)
        if category:
            conn.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                [category, row_id],
            )
            updated += 1
    return updated
