"""Tests for report queries."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from pymoney.db import get_in_memory_connection


@pytest.fixture
def seeded_conn():
    """In-memory DB pre-seeded with sample data."""
    conn = get_in_memory_connection()

    # Seed transactions
    conn.execute("""
        INSERT INTO transactions
            (id, date, description, amount, account, category)
        VALUES
            ('tx-1', '2024-03-05', 'TRADER JOE''S', -55.00, 'Chase', 'Groceries'),
            ('tx-2', '2024-03-10', 'STARBUCKS', -8.50, 'Chase', 'Restaurants'),
            ('tx-3', '2024-03-15', 'COMCAST', -99.00, 'Chase', 'Utilities'),
            ('tx-4', '2024-02-20', 'TRADER JOE''S', -60.00, 'Chase', 'Groceries'),
            ('tx-5', '2024-03-20', 'PAYROLL', 5000.00, 'Chase', 'Paycheck')
    """)

    # Seed categories
    conn.execute("""
        INSERT INTO categories (name, group_name, is_income)
        VALUES
            ('Groceries', 'Food & Dining', FALSE),
            ('Restaurants', 'Food & Dining', FALSE),
            ('Utilities', 'Housing', FALSE),
            ('Paycheck', 'Income', TRUE)
    """)

    # Seed budget
    conn.execute("""
        INSERT INTO budget (id, category, month, amount)
        VALUES
            ('b-1', 'Groceries', 'default', 600.00),
            ('b-2', 'Restaurants', 'default', 300.00),
            ('b-3', 'Utilities', 'default', 200.00)
    """)

    # Seed account_balances
    conn.execute("""
        INSERT INTO account_balances
            (id, date, institution, account, balance)
        VALUES
            ('ab-1', '2024-03-31', 'Chase', 'Chase Checking', 5000.00),
            ('ab-2', '2024-03-31', 'Fidelity', 'Brokerage', 25000.00),
            ('ab-3', '2024-02-29', 'Chase', 'Chase Checking', 3500.00)
    """)

    # Seed net_worth_snapshots
    conn.execute("""
        INSERT INTO net_worth_snapshots
            (id, snapshot_date, total_assets, total_liabilities, net_worth)
        VALUES
            ('2024-02', '2024-02-29', 28500.00, 0.00, 28500.00),
            ('2024-03', '2024-03-31', 30000.00, 0.00, 30000.00)
    """)

    # Seed investment_transactions
    conn.execute("""
        INSERT INTO investment_transactions
            (id, run_date, account, symbol, action, action_type, amount)
        VALUES
            ('inv-1', '2024-03-15', 'Brokerage', 'VOO', 'YOU BOUGHT VOO', 'BUY', -500.00),
            ('inv-2', '2024-03-20', 'Brokerage', 'AAPL', 'YOU BOUGHT AAPL', 'BUY', -200.00)
    """)

    return conn


class TestNetWorthReports:
    def test_net_worth_over_time_columns(self, seeded_conn):
        from pymoney.reports.net_worth import net_worth_over_time
        with patch("pymoney.reports.net_worth.get_connection", return_value=seeded_conn):
            df = net_worth_over_time(months=12)
        assert set(df.columns) >= {"month", "total_assets", "total_liabilities", "net_worth"}

    def test_net_worth_over_time_rows(self, seeded_conn):
        from pymoney.reports.net_worth import net_worth_over_time
        with patch("pymoney.reports.net_worth.get_connection", return_value=seeded_conn):
            df = net_worth_over_time(months=12)
        assert len(df) == 2

    def test_current_net_worth_columns(self, seeded_conn):
        from pymoney.reports.net_worth import current_net_worth
        with patch("pymoney.reports.net_worth.get_connection", return_value=seeded_conn):
            df = current_net_worth()
        assert set(df.columns) >= {"institution", "account", "balance"}

    def test_current_net_worth_latest_balance(self, seeded_conn):
        """Should return the most recent balance for each account."""
        from pymoney.reports.net_worth import current_net_worth
        with patch("pymoney.reports.net_worth.get_connection", return_value=seeded_conn):
            df = current_net_worth()
        chase_row = df[df["account"] == "Chase Checking"]
        assert len(chase_row) == 1
        assert float(chase_row.iloc[0]["balance"]) == 5000.00


class TestSpendingReports:
    def test_spending_by_category_columns(self, seeded_conn):
        from pymoney.reports.spending import spending_by_category
        with patch("pymoney.reports.spending.get_connection", return_value=seeded_conn):
            df = spending_by_category("2024-03")
        assert set(df.columns) >= {"category", "actual", "budget", "variance"}

    def test_spending_by_category_excludes_income(self, seeded_conn):
        from pymoney.reports.spending import spending_by_category
        with patch("pymoney.reports.spending.get_connection", return_value=seeded_conn):
            df = spending_by_category("2024-03")
        categories = df["category"].tolist()
        assert "Paycheck" not in categories

    def test_top_merchants_columns(self, seeded_conn):
        from pymoney.reports.spending import top_merchants
        with patch("pymoney.reports.spending.get_connection", return_value=seeded_conn):
            df = top_merchants("2024-03", n=10)
        assert set(df.columns) >= {"description", "category", "total_amount", "count"}

    def test_top_merchants_limit(self, seeded_conn):
        from pymoney.reports.spending import top_merchants
        with patch("pymoney.reports.spending.get_connection", return_value=seeded_conn):
            df = top_merchants("2024-03", n=2)
        assert len(df) <= 2

    def test_spending_over_time_columns(self, seeded_conn):
        from pymoney.reports.spending import spending_over_time
        with patch("pymoney.reports.spending.get_connection", return_value=seeded_conn):
            df = spending_over_time(months=12)
        assert set(df.columns) >= {"month", "category", "amount"}


class TestInvestmentReports:
    def test_investment_summary_columns(self, seeded_conn):
        from pymoney.reports.investments import investment_summary
        with patch("pymoney.reports.investments.get_connection", return_value=seeded_conn):
            df = investment_summary()
        assert set(df.columns) >= {"account", "symbol", "total_invested", "transaction_count"}

    def test_investment_summary_rows(self, seeded_conn):
        from pymoney.reports.investments import investment_summary
        with patch("pymoney.reports.investments.get_connection", return_value=seeded_conn):
            df = investment_summary()
        assert len(df) == 2

    def test_investment_activity_columns(self, seeded_conn):
        from pymoney.reports.investments import investment_activity
        with patch("pymoney.reports.investments.get_connection", return_value=seeded_conn):
            df = investment_activity("2024-03")
        assert set(df.columns) >= {"run_date", "account", "action_type", "symbol", "amount"}

    def test_investment_activity_filters_by_month(self, seeded_conn):
        from pymoney.reports.investments import investment_activity
        with patch("pymoney.reports.investments.get_connection", return_value=seeded_conn):
            df = investment_activity("2024-03")
        assert len(df) == 2

    def test_investment_activity_empty_month(self, seeded_conn):
        from pymoney.reports.investments import investment_activity
        with patch("pymoney.reports.investments.get_connection", return_value=seeded_conn):
            df = investment_activity("2023-01")
        assert len(df) == 0
