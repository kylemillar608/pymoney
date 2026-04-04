"""Tests for db.py schema initialization."""

from pymoney.db import get_in_memory_connection


EXPECTED_TABLES = {
    "transactions",
    "account_balances",
    "investment_transactions",
    "net_worth_snapshots",
    "categories",
    "budget",
}


def test_all_tables_created(conn):
    """All expected tables exist after schema init."""
    result = conn.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
    """).fetchall()
    tables = {row[0] for row in result}
    assert EXPECTED_TABLES <= tables


def test_schema_init_idempotent():
    """Calling init_schema twice does not raise or duplicate tables."""
    from pymoney.db import init_schema

    conn = get_in_memory_connection()
    # Second call should be a no-op (IF NOT EXISTS)
    init_schema(conn)

    result = conn.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
    """).fetchall()
    tables = {row[0] for row in result}
    assert EXPECTED_TABLES <= tables


def test_transactions_columns(conn):
    """transactions table has expected columns."""
    cols = {
        row[0]
        for row in conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'transactions'
        """).fetchall()
    }
    expected = {"id", "date", "description", "amount", "category", "account", "manually_overridden"}
    assert expected <= cols


def test_investment_transactions_columns(conn):
    """investment_transactions table has expected columns."""
    cols = {
        row[0]
        for row in conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'investment_transactions'
        """).fetchall()
    }
    expected = {"id", "run_date", "action", "action_type", "symbol", "amount"}
    assert expected <= cols
