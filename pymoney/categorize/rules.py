"""Rule-based categorization engine driven by config/categories.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    import duckdb

from pymoney.db import get_connection

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "categories.yaml"


def _load_rules(config_path: Path | None = None) -> list[dict[str, Any]]:
    """Load categories and their rules from YAML config."""
    path = config_path or _CONFIG_PATH
    with path.open() as f:
        data = yaml.safe_load(f)
    return data.get("categories", [])


def _eval_leaf(
    rule: dict[str, Any],
    desc: str,
    full_desc: str,
    account: str,
    institution: str,
    amount: float,
) -> bool:
    """Evaluate a single leaf rule against transaction fields."""
    if "contains" in rule:
        keywords = rule["contains"]
        if isinstance(keywords, str):
            keywords = [keywords]
        return any(kw.upper() in desc or kw.upper() in full_desc for kw in keywords)
    if "regex" in rule:
        pattern = rule["regex"]
        return bool(
            re.search(pattern, desc, re.IGNORECASE)
            or re.search(pattern, full_desc, re.IGNORECASE)
        )
    if "account" in rule:
        return rule["account"].upper() in account
    if "institution" in rule:
        return rule["institution"].upper() in institution
    if "amount_gte" in rule:
        return amount >= float(rule["amount_gte"])
    if "amount_lte" in rule:
        return amount <= float(rule["amount_lte"])
    return False


def _eval_rule(
    rule: dict[str, Any],
    desc: str,
    full_desc: str,
    account: str,
    institution: str,
    amount: float,
) -> bool:
    """Evaluate one rule item — either a leaf rule or an all_of compound."""
    if "all_of" in rule:
        return all(
            _eval_leaf(sub, desc, full_desc, account, institution, amount)
            for sub in rule["all_of"]
        )
    return _eval_leaf(rule, desc, full_desc, account, institution, amount)


def sync_categories(
    conn: duckdb.DuckDBPyConnection,
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
        conn.execute(
            """
            INSERT INTO categories
                (name, group_name, is_income, is_transfer, hide_from_budget, exclude_from_reports)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [name, group_name, is_income, is_transfer, hide_from_budget, exclude_from_reports],
        )


def apply_rules(
    description: str,
    full_description: str | None = None,
    account: str | None = None,
    institution: str | None = None,
    amount: float | None = None,
    config_path: Path | None = None,
) -> str | None:
    """
    Apply categorization rules to a transaction.

    Top-level rules within a category are OR'd; all_of items within a rule are AND'd.
    Returns the first matching category name, or None if no rule matches.
    """
    categories = _load_rules(config_path)
    desc = description.upper()
    full_desc = (full_description or "").upper()
    acct = (account or "").upper()
    inst = (institution or "").upper()
    amt = float(amount) if amount is not None else 0.0

    for category in categories:
        for rule in category.get("rules", []):
            if _eval_rule(rule, desc, full_desc, acct, inst, amt):
                return category["name"]
    return None


def categorize_uncategorized(
    db_path: str | None = None,
    config_path: Path | None = None,
) -> int:
    """
    Apply rules to all transactions with NULL or empty category.

    Returns the count of transactions that were categorized.
    """
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount
        FROM transactions
        WHERE category IS NULL OR category = ''
    """).fetchall()

    updated = 0
    for row_id, desc, full_desc, acct, inst, amount in rows:
        category = apply_rules(desc, full_desc, acct, inst, amount, config_path=config_path)
        if category:
            conn.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                [category, row_id],
            )
            updated += 1
    return updated


def categorize_all(
    db_path: str | None = None,
    config_path: Path | None = None,
) -> int:
    """
    Apply rules to ALL transactions, updating category wherever a rule matches.
    Rows that don't match any rule are left unchanged.

    Returns the count of transactions that were updated.
    """
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount
        FROM transactions
    """).fetchall()

    updated = 0
    for row_id, desc, full_desc, acct, inst, amount in rows:
        category = apply_rules(desc, full_desc, acct, inst, amount, config_path=config_path)
        if category:
            conn.execute(
                "UPDATE transactions SET category = ?, manually_overridden = FALSE WHERE id = ?",
                [category, row_id],
            )
            updated += 1
    return updated
