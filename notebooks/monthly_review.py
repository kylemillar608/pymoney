import marimo

__generated_with = "0.3.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from datetime import date

    today = date.today()
    current_month = today.strftime("%Y-%m")
    return mo, today, current_month


@app.cell
def _(mo, current_month, today):
    mo.md(f"""
    # Monthly Review — {current_month}

    _Last updated: {today}_
    """)
    return


@app.cell
def _():
    from pymoney.db import get_connection
    conn = get_connection()
    return conn,


@app.cell
def _(mo):
    mo.md("## Net Worth")
    return


@app.cell
def _(conn):
    import plotly.express as px
    from pymoney.reports.net_worth import net_worth_over_time

    nw_df = net_worth_over_time(months=12)
    if not nw_df.empty:
        fig_nw = px.line(
            nw_df,
            x="month",
            y="net_worth",
            title="Net Worth (12 months)",
            labels={"net_worth": "Net Worth ($)", "month": "Month"},
        )
        fig_nw
    return fig_nw, nw_df, px


@app.cell
def _(mo):
    mo.md("## Account Summaries")
    return


@app.cell
def _(mo, conn):
    from pymoney.reports.net_worth import current_net_worth

    balance_df = current_net_worth()
    mo.ui.table(balance_df) if not balance_df.empty else mo.md("_No balance data_")
    return balance_df,


@app.cell
def _(mo):
    mo.md("## Spending vs Budget")
    return


@app.cell
def _(mo, current_month, conn):
    import plotly.graph_objects as go
    from pymoney.reports.spending import spending_by_category

    spend_df = spending_by_category(current_month)
    if not spend_df.empty:
        fig_spend = go.Figure(data=[
            go.Bar(name="Actual", x=spend_df["category"], y=spend_df["actual"]),
            go.Bar(name="Budget", x=spend_df["category"], y=spend_df["budget"]),
        ])
        fig_spend.update_layout(
            barmode="group",
            title=f"Spending vs Budget — {current_month}",
        )
        fig_spend
    return fig_spend, go, spend_df


@app.cell
def _(mo):
    mo.md("## Top Merchants")
    return


@app.cell
def _(mo, current_month, conn):
    from pymoney.reports.spending import top_merchants

    merchants_df = top_merchants(current_month, n=10)
    mo.ui.table(merchants_df) if not merchants_df.empty else mo.md("_No transaction data_")
    return merchants_df,


@app.cell
def _(mo):
    mo.md("## Investment Activity")
    return


@app.cell
def _(mo, current_month, conn):
    from pymoney.reports.investments import investment_activity

    inv_df = investment_activity(current_month)
    mo.ui.table(inv_df) if not inv_df.empty else mo.md("_No investment activity this month_")
    return inv_df,


@app.cell
def _(mo):
    mo.md("""
    ## Notes

    _Add monthly notes here._
    """)
    return


if __name__ == "__main__":
    app.run()
