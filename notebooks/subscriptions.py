import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return mo,


@app.cell
def _(mo):
    from pymoney.db import get_connection

    conn = get_connection()
    mo.md("# Subscriptions")
    return conn,


@app.cell
def _(conn, mo):
    from pymoney.subscriptions import get_subscriptions

    _subs = get_subscriptions(conn)

    if not _subs:
        mo.stop(True, mo.md("_No active subscriptions detected. Make sure transactions are categorized as 'Subscriptions'._"))

    _monthly_total = sum(s["monthly_equivalent"] for s in _subs)
    _annual_total = _monthly_total * 12

    mo.hstack([
        mo.stat(value=str(len(_subs)), label="Active Subscriptions", bordered=True),
        mo.stat(value=f"${_monthly_total:,.2f}", label="Monthly Cost", bordered=True),
        mo.stat(value=f"${_annual_total:,.0f}", label="Annual Cost", bordered=True),
    ], justify="start")
    return _subs,


@app.cell
def _(_subs, mo):
    import pandas as pd
    from datetime import date

    _today = date.today()
    _rows = []
    for _s in _subs:
        _days_until = (_s["next_expected"] - _today).days
        if _days_until < 0:
            _due = f"overdue {abs(_days_until)}d"
        elif _days_until == 0:
            _due = "today"
        else:
            _due = f"in {_days_until}d"

        _cadence = _s["cadence"]
        if _s["cadence_estimated"]:
            _cadence += " (est.)"

        _rows.append({
            "Name": _s["name"],
            "Cadence": _cadence,
            "Last Paid": str(_s["last_paid"]),
            "Last Amount": f"${_s['last_amount']:,.2f}",
            "Avg Amount": f"${_s['avg_amount']:,.2f}",
            "Next Expected": f"{_s['next_expected']} ({_due})",
            "Mo. Equiv.": f"${_s['monthly_equivalent']:,.2f}",
            "# Payments": _s["payment_count"],
        })

    mo.ui.table(pd.DataFrame(_rows), selection=None)
    return pd,


if __name__ == "__main__":
    app.run()
