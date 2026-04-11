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
    from pymoney.budget import sync_budget
    from pymoney.categorize.rules import sync_categories
    from pymoney.db import get_connection

    conn = get_connection()
    sync_categories(conn)
    sync_budget(conn)
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
    mo.md("## Cash Flow")


@app.cell
def _(window_slider):
    from pymoney.reports.spending import get_monthly_cash_flow

    cf_data = get_monthly_cash_flow(window_months=window_slider.value)
    return cf_data,


@app.cell
def _(cf_data, mo):
    import plotly.graph_objects as go

    if cf_data:
        _months = [d["month"] for d in cf_data]
        _income = [d["income"] for d in cf_data]
        _expenses = [d["expenses"] for d in cf_data]
        _cash_flow = [d["cash_flow"] for d in cf_data]

        _fig = go.Figure()
        _fig.add_trace(go.Bar(
            name="Income", x=_months, y=_income,
            marker_color="seagreen", offsetgroup=0,
        ))
        _fig.add_trace(go.Bar(
            name="Expenses", x=_months, y=_expenses,
            marker_color="crimson", offsetgroup=1,
        ))
        _fig.add_trace(go.Scatter(
            name="Cash Flow", x=_months, y=_cash_flow,
            mode="lines+markers",
            line=dict(color="steelblue", width=2),
        ))
        _fig.update_layout(
            barmode="group",
            xaxis_title="Month",
            yaxis_title="Amount ($)",
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=40),
        )
        _display = mo.ui.plotly(_fig)
    else:
        _display = mo.md("_No cash flow data available. Run `pymoney ingest tiller` first._")

    _display
    return go,


# ── Section 2: Aggregate Stats ────────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Aggregate Stats")


@app.cell
def _(cf_data, mo):
    import statistics

    if not cf_data or len(cf_data) < 2:
        _display = mo.md("_Not enough data for aggregate stats (need at least 2 months)._")
    else:
        _incomes = [d["income"] for d in cf_data]
        _expenses = [d["expenses"] for d in cf_data]
        _flows = [d["cash_flow"] for d in cf_data]

        def _trimmed_stats(series):
            s = sorted(series)
            trimmed = s[1:-1] if len(s) >= 3 else s
            mean = sum(trimmed) / len(trimmed)
            variance = sum((x - mean) ** 2 for x in trimmed) / len(trimmed)
            std = variance ** 0.5
            return mean, std, len(trimmed)

        _avg_i, _std_i, _n = _trimmed_stats(_incomes)
        _avg_e, _std_e, _ = _trimmed_stats(_expenses)
        _avg_f, _std_f, _ = _trimmed_stats(_flows)
        _caption = f"Based on {_n} months (trimmed)"

        _display = mo.hstack([
            mo.stat(
                value=f"${_avg_i:,.0f}",
                label="Avg Monthly Income",
                caption=f"± ${_std_i:,.0f} · {_caption}",
                bordered=True,
            ),
            mo.stat(
                value=f"${_avg_e:,.0f}",
                label="Avg Monthly Expenses",
                caption=f"± ${_std_e:,.0f} · {_caption}",
                bordered=True,
            ),
            mo.stat(
                value=f"${_avg_f:,.0f}",
                label="Avg Cash Flow",
                caption=f"± ${_std_f:,.0f} · {_caption}",
                bordered=True,
            ),
        ])

    _display
    return statistics,


# ── Section 3: Category Spotlight ─────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Category Spotlight")


@app.cell
def _(window_slider):
    from pymoney.reports.spending import get_category_spotlight

    spotlight = get_category_spotlight(window_months=window_slider.value)
    return spotlight,


@app.cell
def _(spotlight, mo):
    import pandas as pd

    if spotlight:
        _rows = []
        for item in spotlight:
            _budget_str = f"${item['budget']:,.0f}" if item['budget'] else "—"
            _rows.append({
                "Category": item["category"],
                "Group": item["group"] or "—",
                "Signal": f"{item['signal']} {item['direction']}",
                "This Month": f"${item['this_month_spend']:,.0f}",
                "Hist. Avg": f"${item['historical_avg']:,.0f}",
                "Budget": _budget_str,
            })
        _display = mo.ui.table(pd.DataFrame(_rows), selection=None)
    else:
        _display = mo.md("_No category signals detected._")

    _display
    return pd,


if __name__ == "__main__":
    app.run()
