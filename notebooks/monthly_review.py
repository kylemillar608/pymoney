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
    from pymoney.accounts import sync_accounts
    from pymoney.budget import sync_budget
    from pymoney.categorize.rules import sync_categories
    from pymoney.db import get_connection

    conn = get_connection()
    sync_categories(conn)
    sync_accounts(conn)
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


# ── Section 1: Balances & Net Worth ──────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Balances & Net Worth")


@app.cell
def _(conn, mo):
    _rows = conn.execute("""
        SELECT
            ab.account,
            ab.institution,
            ab.balance,
            COALESCE(a.type, 'other')  AS type,
            COALESCE(a.class, 'asset') AS class
        FROM account_balances ab
        LEFT JOIN accounts a ON a.name = ab.account
        WHERE (ab.account, ab.date) IN (
            SELECT account, MAX(date) FROM account_balances GROUP BY account
        )
        ORDER BY class DESC, type, ab.account
    """).fetchall()

    _TYPE_ORDER = ["cash", "holding", "investment", "retirement", "credit", "other"]

    if _rows:
        from collections import defaultdict
        _grouped: dict = defaultdict(lambda: defaultdict(list))
        for _acct, _inst, _bal, _type, _cls in _rows:
            _grouped[_cls][_type].append((_acct, float(_bal)))

        _sections = []
        for _cls in ["asset", "liability"]:
            if _cls not in _grouped:
                continue
            _cls_label = "Assets" if _cls == "asset" else "Liabilities"
            _cls_sign = 1 if _cls == "asset" else -1
            _cls_total = sum(b for types in _grouped[_cls].values() for _, b in types)
            _type_groups = []
            for _type in _TYPE_ORDER:
                if _type not in _grouped[_cls]:
                    continue
                _tiles = [
                    mo.stat(value=f"${b:,.0f}", label=a, caption=_type, bordered=True)
                    for a, b in _grouped[_cls][_type]
                ]
                _type_groups.append(mo.vstack([
                    mo.md(f"<span style='font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--gray-9)'>{_type}</span>"),
                    mo.hstack(_tiles, justify="start"),
                ]))
            _sections.append(mo.vstack([
                mo.md(f"**{_cls_label}** — ${_cls_sign * _cls_total:,.0f}"),
                mo.hstack(_type_groups, justify="start"),
            ]))

        _assets = sum(float(b) for _, _, b, _, cls in _rows if cls == "asset")
        _liabs  = sum(float(b) for _, _, b, _, cls in _rows if cls == "liability")
        _nw_tile = mo.stat(
            value=f"${_assets - _liabs:,.0f}",
            label="Net Worth",
            caption=f"assets ${_assets:,.0f} · liabilities ${_liabs:,.0f}",
            bordered=True,
        )
        _display = mo.vstack([*_sections, _nw_tile])
    else:
        _display = mo.md("_No balance data. Run `pymoney ingest tiller` first._")

    _display


@app.cell
def _(conn, mo):
    import plotly.graph_objects as go

    _rows = conn.execute("""
        WITH latest_per_month AS (
            SELECT
                strftime(date, '%Y-%m') AS month,
                account,
                balance,
                ROW_NUMBER() OVER (
                    PARTITION BY strftime(date, '%Y-%m'), account
                    ORDER BY date DESC
                ) AS rn
            FROM account_balances
        )
        SELECT month, SUM(balance) AS net_worth
        FROM latest_per_month
        WHERE rn = 1
        GROUP BY month
        ORDER BY month
    """).fetchall()

    if _rows:
        _months = [r[0] for r in _rows]
        _values = [float(r[1]) for r in _rows]
        _fig = go.Figure()
        _fig.add_trace(go.Scatter(
            x=_months, y=_values,
            mode="lines+markers",
            line=dict(color="steelblue", width=2),
            fill="tozeroy",
            fillcolor="rgba(70,130,180,0.1)",
        ))
        _fig.update_layout(
            xaxis_title="Month",
            yaxis_title="Net Worth ($)",
            margin=dict(t=30),
        )
        _nw_display = mo.ui.plotly(_fig)
    else:
        _nw_display = mo.md("_No balance data available._")

    _nw_display
    return go,


# ── Section 2: Monthly Cash Flow ──────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Cash Flow")


@app.cell
def _(window_slider):
    from pymoney.reports.spending import get_monthly_cash_flow

    cf_data = get_monthly_cash_flow(window_months=window_slider.value)
    return cf_data,


@app.cell
def _(cf_data, go, mo):
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


# ── Section 3: Aggregate Stats ────────────────────────────────────────────────

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


# ── Section 4: Category Spotlight ─────────────────────────────────────────────

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

    _key = mo.callout(mo.md(
        "**SPIKE** — this month's spend is ≥1.5 std deviations from your historical average  \n"
        "**DRIFT** — 3-month average is >25% above or below budget  \n"
        "**CHRONIC** — spending has been over budget >60% of months (or under <20%)"
    ), kind="info")

    mo.vstack([_display, _key])
    return pd,


# ── Section 5: Recurring Payments ─────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Recurring Payments")


@app.cell
def _(conn, mo, pd):
    from datetime import date as _date
    from pymoney.subscriptions import get_subscriptions

    _subs = get_subscriptions(conn)

    if not _subs:
        mo.stop(True, mo.md("_No active recurring payments detected._"))

    _monthly_total = sum(s["monthly_equivalent"] for s in _subs)

    _summary = mo.hstack([
        mo.stat(value=str(len(_subs)), label="Active Recurring", bordered=True),
        mo.stat(value=f"${_monthly_total:,.2f}", label="Monthly Cost", bordered=True),
        mo.stat(value=f"${_monthly_total * 12:,.0f}", label="Annual Cost", bordered=True),
    ], justify="start")

    _today = _date.today()
    _rows = []
    for _s in _subs:
        _days_until = (_s["next_expected"] - _today).days
        if _days_until < 0:
            _due = f"overdue {abs(_days_until)}d"
        elif _days_until == 0:
            _due = "today"
        else:
            _due = f"in {_days_until}d"

        _cadence = _s["cadence"] + (" (est.)" if _s["cadence_estimated"] else "")
        _rows.append({
            "Name": _s["name"],
            "Cadence": _cadence,
            "Last Paid": str(_s["last_paid"]),
            "Last Amount": f"${_s['last_amount']:,.2f}",
            "Avg Amount": f"${_s['avg_amount']:,.2f}",
            "Next Expected": f"{_s['next_expected']} ({_due})",
            "Mo. Equiv.": f"${_s['monthly_equivalent']:,.2f}",
        })

    mo.vstack([_summary, mo.ui.table(pd.DataFrame(_rows), selection=None)])


# ── Section 6: Investments ────────────────────────────────────────────────────

@app.cell
def _(mo):
    mo.md("## Investments")


@app.cell
def _(conn):
    from pymoney.reports.investments import (
        fetch_current_prices,
        get_brokerage_value_history,
        get_contributions_history,
        get_dividends,
        get_holdings,
        get_portfolio_history,
        load_asset_classes,
    )

    _portfolio_history = get_portfolio_history(conn)
    _holdings_raw = get_holdings(conn)
    _contributions_history = get_contributions_history(conn)
    _brokerage_value_history = get_brokerage_value_history(conn)
    _dividends = get_dividends(conn)
    _asset_classes_map = load_asset_classes()

    portfolio_history = _portfolio_history
    holdings_raw = _holdings_raw
    contributions_history = _contributions_history
    brokerage_value_history = _brokerage_value_history
    dividends = _dividends
    asset_classes_map = _asset_classes_map
    return (
        asset_classes_map,
        brokerage_value_history,
        contributions_history,
        dividends,
        fetch_current_prices,
        holdings_raw,
        portfolio_history,
    )


@app.cell
def _(asset_classes_map, fetch_current_prices, holdings_raw, portfolio_history):
    import pandas as _pd_inv

    _has_holdings = not holdings_raw.empty

    if _has_holdings:
        _prices = fetch_current_prices(holdings_raw["symbol"].tolist())
        _h = holdings_raw.copy()
        _h["current_price"] = _h["symbol"].map(_prices)
        _mask = _h["current_price"].isna()
        _h.loc[_mask, "current_price"] = _h.loc[_mask, "avg_cost_per_share"]
        _h["current_value"] = _h["shares"] * _h["current_price"]
        _h["unrealized_gain"] = _h["current_value"] - _h["cost_basis"]
        _h["return_pct"] = (_h["unrealized_gain"] / _h["cost_basis"]) * 100
        _h["asset_class"] = _h["symbol"].map(asset_classes_map).fillna("Other")
        _h["pct_of_portfolio"] = _h["current_value"] / _h["current_value"].sum() * 100
        inv_holdings = _h
        inv_total_brokerage = float(_h["current_value"].sum())
        inv_total_cost = float(_h["cost_basis"].sum())
        inv_total_unrealized = inv_total_brokerage - inv_total_cost
        inv_total_return_pct = (inv_total_unrealized / inv_total_cost * 100) if inv_total_cost > 0 else 0.0
    else:
        inv_holdings = holdings_raw
        inv_total_brokerage = 0.0
        inv_total_cost = None
        inv_total_unrealized = None
        inv_total_return_pct = None

    _latest_month = portfolio_history["month"].max()
    _latest = portfolio_history[portfolio_history["month"] == _latest_month]
    inv_total_portfolio = float(_latest["balance"].sum())
    inv_has_holdings = _has_holdings
    return (
        inv_has_holdings,
        inv_holdings,
        inv_total_brokerage,
        inv_total_cost,
        inv_total_portfolio,
        inv_total_return_pct,
        inv_total_unrealized,
    )


@app.cell
def _(
    inv_has_holdings,
    inv_holdings,
    inv_total_brokerage,
    inv_total_cost,
    inv_total_portfolio,
    inv_total_return_pct,
    inv_total_unrealized,
    mo,
):
    _tiles = [
        mo.stat(value=f"${inv_total_portfolio:,.0f}", label="Total Portfolio", bordered=True),
        mo.stat(value=f"${inv_total_brokerage:,.0f}", label="Brokerage Value", bordered=True),
    ]
    if inv_total_cost is not None:
        _sign = "+" if inv_total_unrealized >= 0 else ""
        _tiles += [
            mo.stat(value=f"${inv_total_cost:,.0f}", label="Cost Basis", bordered=True),
            mo.stat(value=f"{_sign}${inv_total_unrealized:,.0f}", label="Unrealized Gain/Loss", bordered=True),
            mo.stat(value=f"{_sign}{inv_total_return_pct:.1f}%", label="Total Return", bordered=True),
        ]
    mo.hstack(_tiles, justify="start")


@app.cell
def _(asset_classes_map, go, inv_has_holdings, inv_holdings, mo, portfolio_history):
    import pandas as _pd_alloc

    _latest_bal = portfolio_history[portfolio_history["month"] == portfolio_history["month"].max()]
    _latest_bal = _latest_bal[_latest_bal["balance"] > 0]

    _fig_accounts = go.Figure(go.Pie(
        labels=_latest_bal["account"],
        values=_latest_bal["balance"],
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
        sort=True,
    ))
    _fig_accounts.update_layout(
        title="By Account", showlegend=False,
        margin=dict(t=48, b=8, l=8, r=8), height=340,
    )

    if inv_has_holdings and asset_classes_map:
        _ac = inv_holdings.groupby("asset_class")["current_value"].sum().reset_index()
        _fig_class = go.Figure(go.Pie(
            labels=_ac["asset_class"], values=_ac["current_value"],
            hole=0.45, textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>", sort=True,
        ))
        _fig_class.update_layout(
            title="By Asset Class", showlegend=False,
            margin=dict(t=48, b=8, l=8, r=8), height=340,
        )

        _top = inv_holdings.nlargest(10, "current_value").copy()
        _other_val = inv_holdings["current_value"].sum() - _top["current_value"].sum()
        if _other_val > 1:
            _top = _pd_alloc.concat([_top, _pd_alloc.DataFrame([{"symbol": "Other", "current_value": _other_val}])])
        _fig_ticker = go.Figure(go.Pie(
            labels=_top["symbol"], values=_top["current_value"],
            hole=0.45, textinfo="label+percent",
            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>", sort=True,
        ))
        _fig_ticker.update_layout(
            title="By Ticker", showlegend=False,
            margin=dict(t=48, b=8, l=8, r=8), height=340,
        )
        mo.hstack([mo.ui.plotly(_fig_accounts), mo.ui.plotly(_fig_class), mo.ui.plotly(_fig_ticker)], justify="start")
    else:
        mo.ui.plotly(_fig_accounts)


@app.cell
def _(go, mo, portfolio_history):
    _ACCT_ORDER = ["401k", "Roth IRA", "Brokerage", "Temp Equity", "Equity Awards"]
    _pivot = (
        portfolio_history.pivot(index="month", columns="account", values="balance")
        .ffill().fillna(0)
    )
    _fig_hist = go.Figure()
    for _acct in _ACCT_ORDER:
        if _acct in _pivot.columns and _pivot[_acct].sum() > 0:
            _fig_hist.add_trace(go.Scatter(
                x=_pivot.index, y=_pivot[_acct], name=_acct,
                stackgroup="one", mode="none",
                hovertemplate=f"{_acct}: $%{{y:,.0f}}<extra></extra>",
            ))
    _fig_hist.update_layout(
        title="Portfolio Value Over Time",
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=64, b=40, l=60, r=20), height=380,
    )
    mo.ui.plotly(_fig_hist)


@app.cell
def _(brokerage_value_history, contributions_history, go, inv_has_holdings, mo):
    import pandas as _pd_contrib

    if not inv_has_holdings or contributions_history.empty or brokerage_value_history.empty:
        mo.stop(True)

    # Monthly cumulative contributions (all history from first BUY)
    _contrib = contributions_history.copy()
    _contrib["month"] = _pd_contrib.to_datetime(_contrib["date"]).dt.strftime("%Y-%m")
    _monthly_contrib = (
        _contrib.groupby("month")["daily_contributions"].sum()
        .cumsum().reset_index()
        .rename(columns={"daily_contributions": "cumulative_contributions"})
    )

    # Merge reconstructed brokerage value with cumulative contributions
    _merged = brokerage_value_history.merge(_monthly_contrib, on="month", how="left")
    _merged["cumulative_contributions"] = _merged["cumulative_contributions"].ffill().fillna(0)
    _merged["market_growth"] = _merged["value"] - _merged["cumulative_contributions"]

    _fig_contrib = go.Figure()
    _fig_contrib.add_trace(go.Scatter(
        x=_merged["month"], y=_merged["cumulative_contributions"],
        name="Contributions", stackgroup="one", mode="none",
        hovertemplate="Contributions: $%{y:,.0f}<extra></extra>",
    ))
    _fig_contrib.add_trace(go.Scatter(
        x=_merged["month"], y=_merged["market_growth"],
        name="Market Growth", stackgroup="one", mode="none",
        hovertemplate="Market Growth: $%{y:,.0f}<extra></extra>",
    ))
    _fig_contrib.update_layout(
        title="Contributions vs. Market Growth — Brokerage",
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=64, b=40, l=60, r=20), height=360,
    )
    mo.ui.plotly(_fig_contrib)


@app.cell
def _(go, inv_has_holdings, mo, dividends):
    import pandas as _pd_div

    if not inv_has_holdings or dividends.empty:
        mo.stop(True)

    _total_div = float(dividends["amount"].sum())
    _by_ticker = dividends.groupby("symbol")["amount"].sum().sort_values(ascending=False)

    _fig_div = go.Figure(go.Bar(
        x=_by_ticker.index, y=_by_ticker.values,
        hovertemplate="%{x}: $%{y:,.2f}<extra></extra>",
    ))
    _fig_div.update_layout(
        title="Dividend Income by Ticker",
        yaxis_tickprefix="$", yaxis_tickformat=",.0f",
        margin=dict(t=48, b=40, l=60, r=20), height=300,
    )

    _recent = dividends.head(20).copy()
    _recent["date"] = _pd_div.to_datetime(_recent["date"]).dt.strftime("%Y-%m-%d")
    _recent["amount"] = _recent["amount"].map("${:,.2f}".format)

    mo.accordion({
        f"Dividends — ${_total_div:,.2f} total": mo.vstack([
            mo.ui.plotly(_fig_div),
            mo.ui.table(_recent, selection=None),
        ])
    })


@app.cell
def _(inv_has_holdings, inv_holdings, mo, pd):
    if not inv_has_holdings:
        mo.stop(True)

    _display = pd.DataFrame({
        "Symbol": inv_holdings["symbol"],
        "Asset Class": inv_holdings.get("asset_class", "—"),
        "Shares": inv_holdings["shares"].map("{:.4f}".format),
        "Avg Cost": inv_holdings["avg_cost_per_share"].map("${:,.2f}".format),
        "Price": inv_holdings["current_price"].map("${:,.2f}".format),
        "Value": inv_holdings["current_value"].map("${:,.0f}".format),
        "Gain/Loss": inv_holdings["unrealized_gain"].map(
            lambda x: f"+${x:,.0f}" if x >= 0 else f"-${abs(x):,.0f}"
        ),
        "Return": inv_holdings["return_pct"].map(
            lambda x: f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%"
        ),
        "% Portfolio": inv_holdings["pct_of_portfolio"].map("{:.1f}%".format),
    })
    mo.ui.table(_display, selection=None)


# ── Section 7: Transaction Viewer ─────────────────────────────────────────────

@app.cell
def _(conn, mo):
    _categories = ["All"] + [
        r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
    ]
    _accounts = ["All"] + [
        r[0] for r in conn.execute(
            "SELECT DISTINCT account FROM transactions ORDER BY account"
        ).fetchall()
    ]

    tx_cat_filter = mo.ui.dropdown(_categories, value="All", label="Category")
    tx_acct_filter = mo.ui.dropdown(_accounts, value="All", label="Account")
    tx_search_filter = mo.ui.text(placeholder="Search description…", label="Description")
    tx_limit_filter = mo.ui.dropdown(["100", "500", "1000", "All"], value="100", label="Limit")
    return tx_acct_filter, tx_cat_filter, tx_limit_filter, tx_search_filter


@app.cell
def _(conn, mo, pd, tx_acct_filter, tx_cat_filter, tx_limit_filter, tx_search_filter):
    _where = ["1=1"]
    _params = []
    if tx_cat_filter.value != "All":
        _where.append("category = ?")
        _params.append(tx_cat_filter.value)
    if tx_acct_filter.value != "All":
        _where.append("account = ?")
        _params.append(tx_acct_filter.value)
    if tx_search_filter.value.strip():
        _where.append("description ILIKE ?")
        _params.append(f"%{tx_search_filter.value.strip()}%")

    _limit = "" if tx_limit_filter.value == "All" else f"LIMIT {tx_limit_filter.value}"
    _df = conn.execute(f"""
        SELECT date, description, amount, category, account, institution
        FROM transactions
        WHERE {' AND '.join(_where)}
        ORDER BY date DESC, id DESC
        {_limit}
    """, _params).df()

    _net = _df["amount"].sum() if not _df.empty else 0

    mo.accordion({
        "Transaction Viewer": mo.vstack([
            mo.hstack([tx_cat_filter, tx_acct_filter, tx_search_filter, tx_limit_filter], gap="1rem"),
            mo.md(f"**{len(_df):,} transactions** · net `${_net:,.2f}`"),
            mo.ui.table(_df, selection=None),
        ])
    })


if __name__ == "__main__":
    app.run()
