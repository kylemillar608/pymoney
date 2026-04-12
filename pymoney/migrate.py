"""Migration tools for transitioning to rule-based categorization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


def _has_proposed_column(conn: duckdb.DuckDBPyConnection) -> bool:
    """Return True if proposed_category column exists on transactions."""
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'proposed_category'
        """
    ).fetchall()
    return len(rows) > 0


def prepare(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> int:
    """
    Add proposed_category column (if absent) and run rules into it for every transaction.

    Does not touch the existing category column.
    Returns the number of rows that matched a rule.
    """
    from pymoney.categorize.rules import apply_rules

    if not _has_proposed_column(conn):
        conn.execute("ALTER TABLE transactions ADD COLUMN proposed_category VARCHAR")

    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount
        FROM transactions
    """).fetchall()

    matched = 0
    for row_id, desc, full_desc, acct, inst, amount in rows:
        proposed = apply_rules(desc, full_desc, acct, inst, amount, config_path=config_path)
        conn.execute(
            "UPDATE transactions SET proposed_category = ? WHERE id = ?",
            [proposed, row_id],
        )
        if proposed:
            matched += 1
    return matched


def diff(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """
    Return rows where category differs from proposed_category.

    Grouped by (old_category, proposed_category, description), sorted by count desc.
    Excludes rows where both are identical (including both NULL).
    """
    if not _has_proposed_column(conn):
        raise RuntimeError("Run 'pymoney migrate prepare' first.")

    rows = conn.execute("""
        SELECT
            COALESCE(category, '(none)')               AS old_category,
            COALESCE(proposed_category, '(no match)')  AS proposed_category,
            description,
            COUNT(*)                                   AS count
        FROM transactions
        WHERE category IS DISTINCT FROM proposed_category
        GROUP BY category, proposed_category, description
        ORDER BY
            CASE WHEN proposed_category IS NOT NULL THEN 0 ELSE 1 END,
            count DESC
    """).fetchall()

    return [
        {
            "old_category": r[0],
            "proposed_category": r[1],
            "description": r[2],
            "count": r[3],
        }
        for r in rows
    ]


def apply(conn: duckdb.DuckDBPyConnection) -> int:
    """
    Copy proposed_category → category for all rows where proposed_category is set.

    Returns the number of rows updated.
    """
    if not _has_proposed_column(conn):
        raise RuntimeError("Run 'pymoney migrate prepare' first.")

    count_before = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE proposed_category IS NOT NULL"
    ).fetchone()[0]
    conn.execute("""
        UPDATE transactions
        SET category = proposed_category
        WHERE proposed_category IS NOT NULL
    """)
    return count_before


def clean(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop the proposed_category column."""
    if _has_proposed_column(conn):
        conn.execute("ALTER TABLE transactions DROP COLUMN proposed_category")
