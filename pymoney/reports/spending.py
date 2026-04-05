"""Spending report queries."""

from __future__ import annotations

from datetime import date

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


def get_monthly_cash_flow(
    window_months: int = 12,
    db_path: str | None = None,
) -> list[dict]:
    """
    Return monthly cash flow for the rolling window, excluding transfer/excluded categories.

    Returns list of dicts: {month, income, expenses, cash_flow}
    """
    conn = get_connection(db_path)
    df = conn.execute("""
        SELECT
            strftime(t.date, '%Y-%m') AS month,
            SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0.0 END) AS income,
            SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0.0 END) AS expenses
        FROM transactions t
        LEFT JOIN categories c ON c.name = t.category
        WHERE t.date >= CURRENT_DATE - CAST(? AS INTEGER) * INTERVAL '1 month'
          AND (c.is_transfer IS NULL OR c.is_transfer = FALSE)
          AND (c.exclude_from_reports IS NULL OR c.exclude_from_reports = FALSE)
        GROUP BY strftime(t.date, '%Y-%m')
        ORDER BY month
    """, [window_months]).df()

    result = []
    for _, row in df.iterrows():
        income = float(row["income"])
        expenses = float(row["expenses"])
        result.append({
            "month": row["month"],
            "income": income,
            "expenses": expenses,
            "cash_flow": income - expenses,
        })
    return result


def get_category_spotlight(
    window_months: int = 12,
    db_path: str | None = None,
) -> list[dict]:
    """
    Return top 5 categories by composite spotlight score (SPIKE, DRIFT, CHRONIC).

    Scores each non-excluded, categorized category using:
    - SPIKE: z-score of this month vs historical (fires at |z| >= 1.5)
    - DRIFT: (3-month avg - budget) / budget (fires at >25% over/under)
    - CHRONIC: fraction of months over budget (fires at >60% or <20%)

    Returns list of dicts: {category, group, signal, direction, this_month_spend,
    historical_avg, budget}
    """
    conn = get_connection(db_path)

    spend_df = conn.execute("""
        SELECT
            strftime(t.date, '%Y-%m') AS month,
            t.category,
            c.group_name AS grp,
            SUM(ABS(t.amount)) AS spend
        FROM transactions t
        LEFT JOIN categories c ON c.name = t.category
        WHERE t.date >= CURRENT_DATE - CAST(? AS INTEGER) * INTERVAL '1 month'
          AND t.amount < 0
          AND t.category IS NOT NULL
          AND t.category != ''
          AND (c.is_transfer IS NULL OR c.is_transfer = FALSE)
          AND (c.exclude_from_reports IS NULL OR c.exclude_from_reports = FALSE)
        GROUP BY strftime(t.date, '%Y-%m'), t.category, c.group_name
        ORDER BY month, t.category
    """, [window_months]).df()

    if spend_df.empty:
        return []

    budget_df = conn.execute("""
        SELECT category, amount AS budget FROM budget WHERE month = 'default'
    """).df()
    budget_dict: dict[str, float] = dict(
        zip(budget_df["category"], budget_df["budget"].astype(float))
    )

    today = date.today()
    if today.month == 1:
        this_month = f"{today.year - 1}-12"
    else:
        this_month = f"{today.year}-{today.month - 1:02d}"

    all_months = sorted(spend_df["month"].unique())
    if this_month not in all_months:
        this_month = all_months[-1]

    group_map: dict[str, str | None] = {}
    for _, row in spend_df.iterrows():
        group_map[row["category"]] = row["grp"]

    result = []

    for category in spend_df["category"].unique():
        cat_series = spend_df[spend_df["category"] == category].set_index("month")["spend"]
        all_cat = cat_series.reindex(all_months, fill_value=0.0)

        this_spend = float(all_cat.get(this_month, 0.0))
        historical = all_cat[all_cat.index != this_month]

        signals: dict[str, float] = {}

        # Signal 1: SPIKE
        if len(historical) >= 2:
            mean_h = float(historical.mean())
            std_h = float(historical.std())
            if std_h > 0:
                z = (this_spend - mean_h) / std_h
                if abs(z) >= 1.5:
                    signals["SPIKE"] = abs(z)

        # Signals 2 & 3 require a configured budget
        budget_val = budget_dict.get(category)
        if budget_val and budget_val > 0:
            last_3 = all_cat.iloc[-3:] if len(all_cat) >= 3 else all_cat
            avg_3 = float(last_3.mean())
            drift = (avg_3 - budget_val) / budget_val
            if abs(drift) > 0.25:
                signals["DRIFT"] = abs(drift)

            months_over = int(sum(1 for v in all_cat if v > budget_val))
            fraction = months_over / len(all_cat)
            if fraction > 0.6 or fraction < 0.2:
                signals["CHRONIC"] = max(fraction, 1.0 - fraction)

        if not signals:
            continue

        best_signal = max(signals, key=signals.__getitem__)
        score = signals[best_signal]

        hist_mean = float(historical.mean()) if len(historical) > 0 else 0.0

        if best_signal == "SPIKE":
            direction = "OVER" if this_spend > hist_mean else "UNDER"
        elif best_signal == "DRIFT":
            avg_3_val = float(all_cat.iloc[-3:].mean()) if len(all_cat) >= 3 else float(all_cat.mean())
            direction = "OVER" if avg_3_val > budget_val else "UNDER"
        else:
            months_over_count = int(sum(1 for v in all_cat if v > (budget_val or 0)))
            fraction_over = months_over_count / len(all_cat)
            direction = "OVER" if fraction_over > 0.6 else "UNDER"

        result.append({
            "category": category,
            "group": group_map.get(category),
            "signal": best_signal,
            "score": score,
            "direction": direction,
            "this_month_spend": this_spend,
            "historical_avg": hist_mean,
            "budget": float(budget_val) if budget_val else None,
        })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:5]


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
