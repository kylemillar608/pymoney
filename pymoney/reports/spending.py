"""Spending report queries."""

from __future__ import annotations

import pandas as pd

from pymoney.db import get_connection


def spending_by_category(month: str, db_path: str | None = None) -> pd.DataFrame:
    """
    Return spending vs budget for a given month (YYYY-MM).

    Columns: category, group, actual, budget, variance
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        WITH actuals AS (
            SELECT
                t.category,
                SUM(ABS(t.amount)) AS actual
            FROM transactions t
            LEFT JOIN categories c ON c.name = t.category
            WHERE strftime(t.date, '%Y-%m') = ?
              AND t.amount < 0
              AND (c.is_income IS NULL OR c.is_income = FALSE)
              AND (c.is_transfer IS NULL OR c.is_transfer = FALSE)
              AND (c.hide_from_budget IS NULL OR c.hide_from_budget = FALSE)
            GROUP BY t.category
        ),
        budgets AS (
            SELECT category, amount AS budget
            FROM budget
            WHERE month = ? OR month = 'default'
        )
        SELECT
            COALESCE(a.category, b.category) AS category,
            c.group_name AS group,
            COALESCE(a.actual, 0) AS actual,
            COALESCE(b.budget, 0) AS budget,
            COALESCE(b.budget, 0) - COALESCE(a.actual, 0) AS variance
        FROM actuals a
        FULL OUTER JOIN budgets b ON a.category = b.category
        LEFT JOIN categories c ON c.name = COALESCE(a.category, b.category)
        ORDER BY actual DESC
    """, [month, month]).df()
    return df


def spending_over_time(months: int = 12, db_path: str | None = None) -> pd.DataFrame:
    """
    Return monthly spending by category for the past N months.

    Columns: month, category, amount
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            strftime(date, '%Y-%m') AS month,
            category,
            SUM(ABS(amount)) AS amount
        FROM transactions
        WHERE amount < 0
          AND date >= (CURRENT_DATE - CAST(? AS INTEGER) * INTERVAL '1 month')
        GROUP BY strftime(date, '%Y-%m'), category
        ORDER BY month DESC, amount DESC
    """, [months]).df()
    return df


def top_merchants(month: str, n: int = 10, db_path: str | None = None) -> pd.DataFrame:
    """
    Return top N merchants by spending for a given month.

    Columns: description, category, total_amount, count
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            description,
            category,
            SUM(ABS(amount)) AS total_amount,
            COUNT(*) AS count
        FROM transactions
        WHERE strftime(date, '%Y-%m') = ?
          AND amount < 0
        GROUP BY description, category
        ORDER BY total_amount DESC
        LIMIT ?
    """, [month, n]).df()
    return df
