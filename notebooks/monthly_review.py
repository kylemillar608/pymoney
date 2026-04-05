import marimo

__generated_with = "0.3.0"
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
    mo.md("## Section 1 — Monthly Cash Flow")
    return


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
            name="Income",
            x=_months,
            y=_income,
            marker_color="seagreen",
            offsetgroup=0,
        ))
        _fig.add_trace(go.Bar(
            name="Expenses",
            x=_months,
            y=_expenses,
            marker_color="crimson",
            offsetgroup=1,
        ))
        _fig.add_trace(go.Scatter(
            name="Cash Flow",
            x=_months,
            y=_cash_flow,
            mode="lines+markers",
            line=dict(color="steelblue", width=2),
        ))
        _fig.update_layout(
            barmode="group",
            title="Monthly Cash Flow",
            xaxis_title="Month",
            yaxis_title="Amount ($)",
            legend=dict(orientation="h", y=1.1),
        )
        _fig
    else:
        mo.md("_No cash flow data available_")
    return go,


# ── Section 2: Aggregate Stats ────────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Section 2 — Aggregate Stats")
    return


@app.cell
def _(cf_data, mo):
    import numpy as np

    if not cf_data:
        mo.md("_No data available_")
    else:
        _incomes = [d["income"] for d in cf_data]
        _expenses = [d["expenses"] for d in cf_data]
        _flows = [d["cash_flow"] for d in cf_data]

        if len(cf_data) >= 3:
            def _trim(series):
                s = sorted(series)
                return s[1:-1]

            _ti = _trim(_incomes)
            _te = _trim(_expenses)
            _tf = _trim(_flows)
            _n = len(_ti)
            _caption_suffix = f"Based on {_n} months (trimmed)"
        else:
            _ti, _te, _tf = _incomes, _expenses, _flows
            _n = len(_ti)
            _caption_suffix = f"Based on {_n} months"

        _avg_i = float(np.mean(_ti))
        _std_i = float(np.std(_ti))
        _avg_e = float(np.mean(_te))
        _std_e = float(np.std(_te))
        _avg_f = float(np.mean(_tf))
        _std_f = float(np.std(_tf))

        mo.hstack([
            mo.stat(
                value=f"${_avg_i:,.0f}",
                label="Avg Monthly Income",
                caption=f"± ${_std_i:,.0f} · {_caption_suffix}",
                bordered=True,
            ),
            mo.stat(
                value=f"${_avg_e:,.0f}",
                label="Avg Monthly Expenses",
                caption=f"± ${_std_e:,.0f} · {_caption_suffix}",
                bordered=True,
                target_direction="decrease",
            ),
            mo.stat(
                value=f"${_avg_f:,.0f}",
                label="Avg Cash Flow",
                caption=f"± ${_std_f:,.0f} · {_caption_suffix}",
                bordered=True,
            ),
        ])
    return np,


# ── Section 3: Category Spotlight ────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Section 3 — Category Spotlight")
    return


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
        for _item in spotlight:
            _budget_str = f"${_item['budget']:,.0f}" if _item['budget'] else "—"
            _rows.append({
                "Category": _item["category"],
                "Group": _item["group"] or "—",
                "Signal": f"{_item['signal']} {_item['direction']}",
                "This Month": f"${_item['this_month_spend']:,.0f}",
                "Hist. Avg": f"${_item['historical_avg']:,.0f}",
                "Budget": _budget_str,
            })
        _df = pd.DataFrame(_rows)
        mo.ui.table(_df, selection=None)
    else:
        mo.md("_No categories to spotlight_")
    return pd,


if __name__ == "__main__":
    app.run()
