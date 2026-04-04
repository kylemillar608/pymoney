"""Net worth report queries."""

from __future__ import annotations

import pandas as pd

from pymoney.db import get_connection


def net_worth_over_time(months: int = 12, db_path: str | None = None) -> pd.DataFrame:
    """
    Return monthly net worth summary for the past N months.

    Columns: month, total_assets, total_liabilities, net_worth
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            id AS month,
            total_assets,
            total_liabilities,
            net_worth
        FROM net_worth_snapshots
        ORDER BY snapshot_date DESC
        LIMIT ?
    """, [months]).df()
    return df.sort_values("month")


def current_net_worth(db_path: str | None = None) -> pd.DataFrame:
    """
    Return current balance for all accounts (latest snapshot per account).

    Columns: institution, account, balance
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            institution,
            account,
            balance
        FROM account_balances
        WHERE (account, date) IN (
            SELECT account, MAX(date)
            FROM account_balances
            GROUP BY account
        )
        ORDER BY institution, account
    """).df()
    return df
