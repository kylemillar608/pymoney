import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return mo,


@app.cell
def _(mo):
    from datetime import date

    today = date.today()
    if today.month == 1:
        _current = f"{today.year - 1}-12"
    else:
        _current = f"{today.year}-{today.month - 1:02d}"

    mo.md(f"""
    # Monthly Overview — {_current}

    _Cash flow · aggregate stats · category spotlight_
    """)
    return today,


@app.cell
def _():
    from pymoney.db import get_connection
    from pymoney.categorize.rules import sync_categories

    conn = get_connection()
    sync_categories(conn)
    return conn,


@app.cell
def _(mo):
    window_slider = mo.ui.slider(
        start=6,
        stop=24,
        step=6,
        value=12,
        label="Rolling window (months)",
    )
    window_slider
    return window_slider,


# ── Section 1: Monthly Cash Flow ──────────────────────────────────────────────

@app.cell
def _(mo):
    return mo.md("## Cash Flow"),


@app.cell
def _(window_slider):
    from pymoney.reports.spending import get_monthly_cash_flow

    cf_data = get_monthly_cash_flow(window_months=window_slider.value)
    return cf_data,


@app.cell
def _(cf_data, mo):
    import plotly.graph_objects as go

    if cf_data:
        months = [d["month"] for d in cf_data]
        income = [d["income"] for d in cf_data]
        expenses = [d["expenses"] for d in cf_data]
        cash_flow = [d["cash_flow"] for d in cf_data]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Income", x=months, y=income,
            marker_color="seagreen", offsetgroup=0,
        ))
        fig.add_trace(go.Bar(
            name="Expenses", x=months, y=expenses,
            marker_color="crimson", offsetgroup=1,
        ))
        fig.add_trace(go.Scatter(
            name="Cash Flow", x=months, y=cash_flow,
            mode="lines+markers",
            line=dict(color="steelblue", width=2),
        ))
        fig.update_layout(
            barmode="group",
            xaxis_title="Month",
            yaxis_title="Amount ($)",
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=40),
        )
        _display = mo.ui.plotly(fig)
    else:
        _display = mo.md("_No cash flow data available. Run `pymoney ingest tiller` first._")

    _display
    return go,


# ── Section 2: Aggregate Stats ────────────────────────────────────────────────

@app.cell
def _(mo):
    return mo.md("## Aggregate Stats"),


@app.cell
def _(cf_data, mo):
    import statistics

    if not cf_data or len(cf_data) < 2:
        _display = mo.md("_Not enough data for aggregate stats (need at least 2 months)._")
    else:
        incomes = [d["income"] for d in cf_data]
        expenses = [d["expenses"] for d in cf_data]
        flows = [d["cash_flow"] for d in cf_data]

        def _trimmed_stats(series):
            s = sorted(series)
            trimmed = s[1:-1] if len(s) >= 3 else s
            mean = sum(trimmed) / len(trimmed)
            variance = sum((x - mean) ** 2 for x in trimmed) / len(trimmed)
            std = variance ** 0.5
            return mean, std, len(trimmed)

        avg_i, std_i, n = _trimmed_stats(incomes)
        avg_e, std_e, _ = _trimmed_stats(expenses)
        avg_f, std_f, _ = _trimmed_stats(flows)
        caption = f"Based on {n} months (trimmed)"

        _display = mo.hstack([
            mo.stat(
                value=f"${avg_i:,.0f}",
                label="Avg Monthly Income",
                caption=f"± ${std_i:,.0f} · {caption}",
                bordered=True,
            ),
            mo.stat(
                value=f"${avg_e:,.0f}",
                label="Avg Monthly Expenses",
                caption=f"± ${std_e:,.0f} · {caption}",
                bordered=True,
            ),
            mo.stat(
                value=f"${avg_f:,.0f}",
                label="Avg Cash Flow",
                caption=f"± ${std_f:,.0f} · {caption}",
                bordered=True,
            ),
        ])

    _display
    return statistics,


# ── Section 3: Category Spotlight ─────────────────────────────────────────────

@app.cell
def _(mo):
    return mo.md("## Category Spotlight"),


@app.cell
def _(window_slider):
    from pymoney.reports.spending import get_category_spotlight

    spotlight = get_category_spotlight(window_months=window_slider.value)
    return spotlight,


@app.cell
def _(spotlight, mo):
    import pandas as pd

    if spotlight:
        rows = []
        for item in spotlight:
            budget_str = f"${item['budget']:,.0f}" if item['budget'] else "—"
            rows.append({
                "Category": item["category"],
                "Group": item["group"] or "—",
                "Signal": f"{item['signal']} {item['direction']}",
                "This Month": f"${item['this_month_spend']:,.0f}",
                "Hist. Avg": f"${item['historical_avg']:,.0f}",
                "Budget": budget_str,
            })
        _display = mo.ui.table(pd.DataFrame(rows), selection=None)
    else:
        _display = mo.md("_No category signals detected._")

    _display
    return pd,


if __name__ == "__main__":
    app.run()
