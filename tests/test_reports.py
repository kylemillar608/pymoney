"""Tests for report queries."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from pymoney.db import get_in_memory_connection


def _month_date(months_back: int) -> str:
    """Return YYYY-MM-DD on the 15th of the month N months before today."""
    today = date.today()
    m = today.month - months_back
    y = today.year
    while m <= 0:
        m += 12
        y -= 1
    return f"{y}-{m:02d}-15"


@pytest.fixture
def cf_conn():
    """In-memory DB seeded for cash flow and category spotlight tests."""
    conn = get_in_memory_connection()

    conn.execute("""
        INSERT INTO categories (name, group_name, is_income, is_transfer)
        VALUES
            ('Groceries',   'Food & Dining', FALSE, FALSE),
            ('Restaurants', 'Food & Dining', FALSE, FALSE),
            ('Paycheck',    'Income',        TRUE,  FALSE),
            ('Transfers',   'Transfers',     FALSE, TRUE)
    """)

    conn.execute("""
        INSERT INTO budget (id, category, month, amount)
        VALUES
            ('b-1', 'Groceries',   'default', 600.00),
            ('b-2', 'Restaurants', 'default', 300.00)
    """)

    # Historical grocery amounts with slight variance so std_dev > 0
    grocery_hist = [45, 55, 50, 48, 52, 50, 47, 53, 49, 51, 50]  # months 12..2 back
    tx_params = []
    for idx, months_back in enumerate(range(12, 1, -1)):  # 12, 11, ..., 2
        d = _month_date(months_back)
        g = grocery_hist[idx]
        tx_params += [
            (f"tx-g-{months_back}", d, "TRADER JOES", float(-g), "Chase", "Groceries"),
            (f"tx-r-{months_back}", d, "RESTAURANTS", -400.00, "Chase", "Restaurants"),
            (f"tx-p-{months_back}", d, "PAYROLL", 5000.00, "Chase", "Paycheck"),
        ]

    # "This month" = 1 month back — spike for Groceries, drift for Restaurants
    d1 = _month_date(1)
    tx_params += [
        ("tx-g-1", d1, "TRADER JOES", -200.00, "Chase", "Groceries"),
        ("tx-r-1", d1, "RESTAURANTS", -400.00, "Chase", "Restaurants"),
        ("tx-p-1", d1, "PAYROLL", 5000.00, "Chase", "Paycheck"),
        ("tx-t-1", d1, "TRANSFER", -1000.00, "Chase", "Transfers"),
    ]

    conn.executemany(
        "INSERT INTO transactions (id, date, description, amount, account, category) VALUES (?,?,?,?,?,?)",
        tx_params,
    )
    return conn


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


class TestMonthlyCashFlow:
    def test_returns_list_of_dicts(self, cf_conn):
        from pymoney.reports.spending import get_monthly_cash_flow
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_monthly_cash_flow(window_months=13)
        assert isinstance(result, list)
        assert len(result) > 0
        required_keys = {"month", "income", "expenses", "cash_flow"}
        for row in result:
            assert required_keys <= row.keys()

    def test_cash_flow_arithmetic(self, cf_conn):
        from pymoney.reports.spending import get_monthly_cash_flow
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_monthly_cash_flow(window_months=13)
        for row in result:
            assert abs(row["cash_flow"] - (row["income"] - row["expenses"])) < 0.01

    def test_excludes_transfer_from_expenses(self, cf_conn):
        """Transfer transactions must not inflate expenses."""
        from pymoney.reports.spending import get_monthly_cash_flow
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_monthly_cash_flow(window_months=13)
        # This month (1 month back): groceries $200 + restaurants $400 = $600.
        # If transfers ($1000) were included, expenses would be $1600.
        today = date.today()
        if today.month == 1:
            this_month = f"{today.year - 1}-12"
        else:
            this_month = f"{today.year}-{today.month - 1:02d}"
        this_month_rows = [r for r in result if r["month"] == this_month]
        assert len(this_month_rows) == 1
        assert abs(this_month_rows[0]["expenses"] - 600.0) < 0.01

    def test_income_captured(self, cf_conn):
        """Positive transactions should appear as income."""
        from pymoney.reports.spending import get_monthly_cash_flow
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_monthly_cash_flow(window_months=13)
        for row in result:
            assert row["income"] >= 0
            assert row["expenses"] >= 0


class TestCategorySpotlight:
    def test_returns_at_most_five(self, cf_conn):
        from pymoney.reports.spending import get_category_spotlight
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_category_spotlight(window_months=13)
        assert len(result) <= 5

    def test_required_keys(self, cf_conn):
        from pymoney.reports.spending import get_category_spotlight
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_category_spotlight(window_months=13)
        required = {"category", "group", "signal", "direction", "this_month_spend", "historical_avg", "budget"}
        for row in result:
            assert required <= row.keys()

    def test_spike_detected_for_groceries(self, cf_conn):
        """Groceries has a large z-score spike this month (200 vs ~50 historical)."""
        from pymoney.reports.spending import get_category_spotlight
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_category_spotlight(window_months=13)
        grocery_rows = [r for r in result if r["category"] == "Groceries"]
        assert len(grocery_rows) == 1
        assert grocery_rows[0]["signal"] == "SPIKE"
        assert grocery_rows[0]["direction"] == "OVER"

    def test_drift_detected_for_restaurants(self, cf_conn):
        """Restaurants consistently spends $400 vs $300 budget (33% over = DRIFT)."""
        from pymoney.reports.spending import get_category_spotlight
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_category_spotlight(window_months=13)
        restaurant_rows = [r for r in result if r["category"] == "Restaurants"]
        assert len(restaurant_rows) == 1
        assert restaurant_rows[0]["signal"] in {"DRIFT", "CHRONIC"}
        assert restaurant_rows[0]["direction"] == "OVER"

    def test_excludes_transfer_categories(self, cf_conn):
        """is_transfer categories must never appear in the spotlight."""
        from pymoney.reports.spending import get_category_spotlight
        with patch("pymoney.reports.spending.get_connection", return_value=cf_conn):
            result = get_category_spotlight(window_months=13)
        categories = [r["category"] for r in result]
        assert "Transfers" not in categories

    def test_empty_db_returns_empty_list(self):
        from pymoney.reports.spending import get_category_spotlight
        conn = get_in_memory_connection()
        with patch("pymoney.reports.spending.get_connection", return_value=conn):
            result = get_category_spotlight(window_months=12)
        assert result == []
