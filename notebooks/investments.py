import marimo

__generated_with = "0.22.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import pandas as pd
    import plotly.graph_objects as go
    return go, pd


@app.cell
def _():
    from pymoney.db import get_connection
    conn = get_connection()
    return (conn,)


@app.cell
def _(conn):
    from pymoney.reports.investments import (
        fetch_current_prices,
        get_contributions_history,
        get_dividends,
        get_holdings,
        get_portfolio_history,
        load_asset_classes,
    )

    portfolio_history = get_portfolio_history(conn)
    holdings_raw = get_holdings(conn)
    contributions_history = get_contributions_history(conn)
    dividends = get_dividends(conn)
    asset_classes_map = load_asset_classes()
    return (
        asset_classes_map,
        contributions_history,
        dividends,
        fetch_current_prices,
        holdings_raw,
        portfolio_history,
    )


@app.cell
def _(asset_classes_map, fetch_current_prices, holdings_raw, portfolio_history):
    import pandas as _pd

    has_holdings = not holdings_raw.empty

    if has_holdings:
        _prices = fetch_current_prices(holdings_raw["symbol"].tolist())

        holdings = holdings_raw.copy()
        holdings["current_price"] = holdings["symbol"].map(_prices)

        # Fall back to avg cost for positions without a live price (e.g. money market)
        _mask = holdings["current_price"].isna()
        holdings.loc[_mask, "current_price"] = holdings.loc[_mask, "avg_cost_per_share"]

        holdings["current_value"] = holdings["shares"] * holdings["current_price"]
        holdings["unrealized_gain"] = holdings["current_value"] - holdings["cost_basis"]
        holdings["return_pct"] = (holdings["unrealized_gain"] / holdings["cost_basis"]) * 100
        holdings["asset_class"] = holdings["symbol"].map(asset_classes_map).fillna("Other")
        holdings["pct_of_portfolio"] = (
            holdings["current_value"] / holdings["current_value"].sum() * 100
        )

        total_brokerage_value = float(holdings["current_value"].sum())
        total_cost = float(holdings["cost_basis"].sum())
        total_unrealized = total_brokerage_value - total_cost
        total_return_pct = (total_unrealized / total_cost * 100) if total_cost > 0 else 0.0
    else:
        holdings = holdings_raw
        total_brokerage_value = 0.0
        total_cost = None
        total_unrealized = None
        total_return_pct = None

    # Total portfolio value across all accounts (from account_balances)
    _latest_month = portfolio_history["month"].max()
    _latest = portfolio_history[portfolio_history["month"] == _latest_month]
    total_portfolio_value = float(_latest["balance"].sum())

    return (
        has_holdings,
        holdings,
        total_brokerage_value,
        total_cost,
        total_portfolio_value,
        total_return_pct,
        total_unrealized,
    )


# ── Header ────────────────────────────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Investments")


# ── Summary tiles ─────────────────────────────────────────────────────────────

@app.cell
def _(
    mo,
    total_brokerage_value,
    total_cost,
    total_portfolio_value,
    total_return_pct,
    total_unrealized,
):
    _tiles = [
        mo.stat(value=f"${total_portfolio_value:,.0f}", label="Total Portfolio", bordered=True),
        mo.stat(value=f"${total_brokerage_value:,.0f}", label="Brokerage Value", bordered=True),
    ]
    if total_cost is not None:
        _sign = "+" if total_unrealized >= 0 else ""
        _tiles += [
            mo.stat(value=f"${total_cost:,.0f}", label="Cost Basis", bordered=True),
            mo.stat(
                value=f"{_sign}${total_unrealized:,.0f}",
                label="Unrealized Gain/Loss",
                bordered=True,
            ),
            mo.stat(
                value=f"{_sign}{total_return_pct:.1f}%",
                label="Total Return",
                bordered=True,
            ),
        ]
    mo.hstack(_tiles, justify="start")


# ── Allocation ────────────────────────────────────────────────────────────────

@app.cell
def _(asset_classes_map, go, has_holdings, holdings, mo, portfolio_history):
    import pandas as _pd

    # --- Account allocation (always available) ---
    _latest = portfolio_history[portfolio_history["month"] == portfolio_history["month"].max()]
    _latest = _latest[_latest["balance"] > 0]

    _fig_accounts = go.Figure(go.Pie(
        labels=_latest["account"],
        values=_latest["balance"],
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
        sort=True,
    ))
    _fig_accounts.update_layout(
        title="By Account",
        showlegend=False,
        margin=dict(t=48, b=8, l=8, r=8),
        height=340,
    )

    if has_holdings and asset_classes_map:
        # --- Asset class allocation ---
        _ac = holdings.groupby("asset_class")["current_value"].sum().reset_index()
        _fig_class = go.Figure(go.Pie(
            labels=_ac["asset_class"],
            values=_ac["current_value"],
            hole=0.45,
            textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
            sort=True,
        ))
        _fig_class.update_layout(
            title="By Asset Class",
            showlegend=False,
            margin=dict(t=48, b=8, l=8, r=8),
            height=340,
        )

        # --- Ticker allocation ---
        _top = holdings.nlargest(10, "current_value").copy()
        _other_val = holdings["current_value"].sum() - _top["current_value"].sum()
        if _other_val > 1:
            _top = _pd.concat([
                _top,
                _pd.DataFrame([{"symbol": "Other", "current_value": _other_val}]),
            ])
        _fig_ticker = go.Figure(go.Pie(
            labels=_top["symbol"],
            values=_top["current_value"],
            hole=0.45,
            textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
            sort=True,
        ))
        _fig_ticker.update_layout(
            title="By Ticker",
            showlegend=False,
            margin=dict(t=48, b=8, l=8, r=8),
            height=340,
        )

        mo.hstack([
            mo.ui.plotly(_fig_accounts),
            mo.ui.plotly(_fig_class),
            mo.ui.plotly(_fig_ticker),
        ], justify="start")
    else:
        mo.ui.plotly(_fig_accounts)


# ── Portfolio value over time ─────────────────────────────────────────────────

@app.cell
def _(go, mo, portfolio_history):
    _ACCOUNT_ORDER = ["401k", "Roth IRA", "Brokerage", "Temp Equity", "Equity Awards"]

    _pivot = (
        portfolio_history
        .pivot(index="month", columns="account", values="balance")
        .ffill()
        .fillna(0)
    )

    _fig = go.Figure()
    for _acct in _ACCOUNT_ORDER:
        if _acct in _pivot.columns and _pivot[_acct].sum() > 0:
            _fig.add_trace(go.Scatter(
                x=_pivot.index,
                y=_pivot[_acct],
                name=_acct,
                stackgroup="one",
                mode="none",
                hovertemplate=f"{_acct}: $%{{y:,.0f}}<extra></extra>",
            ))

    _fig.update_layout(
        title="Portfolio Value Over Time",
        xaxis_title=None,
        yaxis_title=None,
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=64, b=40, l=60, r=20),
        height=380,
    )

    mo.ui.plotly(_fig)


# ── Contributions vs. growth (Brokerage) ──────────────────────────────────────

@app.cell
def _(contributions_history, go, has_holdings, mo, portfolio_history):
    import pandas as _pd

    if not has_holdings or contributions_history.empty:
        mo.callout(
            mo.md("Contributions vs. growth chart requires brokerage transaction data."),
            kind="info",
        )
    else:
        # Monthly cumulative contributions
        _contrib = contributions_history.copy()
        _contrib["month"] = _pd.to_datetime(_contrib["date"]).dt.strftime("%Y-%m")
        _monthly_contrib = (
            _contrib.groupby("month")["daily_contributions"]
            .sum()
            .cumsum()
            .reset_index()
            .rename(columns={"daily_contributions": "cumulative_contributions"})
        )

        # Brokerage monthly balance
        _brokerage = portfolio_history[portfolio_history["account"] == "Brokerage"][
            ["month", "balance"]
        ]

        _merged = _brokerage.merge(_monthly_contrib, on="month", how="left")
        _merged["cumulative_contributions"] = _merged["cumulative_contributions"].ffill().fillna(0)
        _merged["market_growth"] = (
            (_merged["balance"] - _merged["cumulative_contributions"]).clip(lower=0)
        )

        _fig = go.Figure()
        _fig.add_trace(go.Scatter(
            x=_merged["month"],
            y=_merged["cumulative_contributions"],
            name="Contributions",
            stackgroup="one",
            mode="none",
            hovertemplate="Contributions: $%{y:,.0f}<extra></extra>",
        ))
        _fig.add_trace(go.Scatter(
            x=_merged["month"],
            y=_merged["market_growth"],
            name="Market Growth",
            stackgroup="one",
            mode="none",
            hovertemplate="Market Growth: $%{y:,.0f}<extra></extra>",
        ))
        _fig.update_layout(
            title="Contributions vs. Market Growth — Brokerage",
            xaxis_title=None,
            yaxis_tickprefix="$",
            yaxis_tickformat=",.0f",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=64, b=40, l=60, r=20),
            height=360,
        )

        mo.ui.plotly(_fig)


# ── Holdings table ────────────────────────────────────────────────────────────

@app.cell
def _(has_holdings, holdings, mo, pd):
    if not has_holdings:
        mo.callout(
            mo.md("No holdings data. Run `pymoney ingest brokerage` to populate."),
            kind="info",
        )
    else:
        _display = pd.DataFrame({
            "Symbol": holdings["symbol"],
            "Asset Class": holdings.get("asset_class", "—"),
            "Shares": holdings["shares"].map("{:.4f}".format),
            "Avg Cost": holdings["avg_cost_per_share"].map("${:,.2f}".format),
            "Price": holdings["current_price"].map("${:,.2f}".format),
            "Value": holdings["current_value"].map("${:,.0f}".format),
            "Gain/Loss": holdings["unrealized_gain"].map(
                lambda x: f"+${x:,.0f}" if x >= 0 else f"-${abs(x):,.0f}"
            ),
            "Return": holdings["return_pct"].map(
                lambda x: f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%"
            ),
            "% Portfolio": holdings["pct_of_portfolio"].map("{:.1f}%".format),
        })
        mo.ui.table(_display, selection=None)


# ── Dividends ─────────────────────────────────────────────────────────────────

@app.cell
def _(dividends, go, mo):
    import pandas as _pd

    if dividends.empty:
        mo.stop(True)

    _total = float(dividends["amount"].sum())
    _by_ticker = dividends.groupby("symbol")["amount"].sum().sort_values(ascending=False)

    _fig = go.Figure(go.Bar(
        x=_by_ticker.index,
        y=_by_ticker.values,
        hovertemplate="%{x}: $%{y:,.2f}<extra></extra>",
    ))
    _fig.update_layout(
        title="Dividend Income by Ticker",
        xaxis_title=None,
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        margin=dict(t=48, b=40, l=60, r=20),
        height=300,
    )

    _recent = dividends.head(20).copy()
    _recent["date"] = _pd.to_datetime(_recent["date"]).dt.strftime("%Y-%m-%d")
    _recent["amount"] = _recent["amount"].map("${:,.2f}".format)

    mo.accordion({
        f"Dividends — ${_total:,.2f} total": mo.vstack([
            mo.ui.plotly(_fig),
            mo.ui.table(_recent, selection=None),
        ])
    })


if __name__ == "__main__":
    app.run()
