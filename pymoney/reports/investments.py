"""Investment report queries."""

from __future__ import annotations

import pandas as pd

from pymoney.db import get_connection


def investment_summary(db_path: str | None = None) -> pd.DataFrame:
    """
    Return aggregate investment position per account/symbol.

    Columns: account, symbol, description, total_invested, transaction_count
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            account,
            symbol,
            description,
            SUM(ABS(COALESCE(amount, 0))) AS total_invested,
            COUNT(*) AS transaction_count
        FROM investment_transactions
        WHERE action_type IN ('BUY', 'REINVESTMENT')
        GROUP BY account, symbol, description
        ORDER BY total_invested DESC
    """).df()
    return df


def investment_activity(month: str, db_path: str | None = None) -> pd.DataFrame:
    """
    Return all investment transactions for a given month (YYYY-MM).

    Columns: run_date, account, action, action_type, symbol, description,
             quantity, price, amount
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            run_date,
            account,
            action,
            action_type,
            symbol,
            description,
            quantity,
            price,
            amount
        FROM investment_transactions
        WHERE strftime(run_date, '%Y-%m') = ?
        ORDER BY run_date DESC
    """, [month]).df()
    return df
