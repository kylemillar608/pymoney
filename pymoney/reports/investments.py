"""Investment report queries and computations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yaml

if TYPE_CHECKING:
    import duckdb

_ASSET_CLASSES_PATH = Path(__file__).parent.parent.parent / "config" / "asset_classes.yaml"
_INVESTMENT_ACCOUNTS = ["Brokerage", "401k", "Roth IRA", "Equity Awards", "Temp Equity"]


def load_asset_classes(config_path: Path | None = None) -> dict[str, str]:
    """Load ticker → asset class mapping. Returns {} if file not found."""
    path = config_path or _ASSET_CLASSES_PATH
    if not path.exists():
        return {}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return {entry["ticker"]: entry["asset_class"] for entry in data.get("asset_classes", [])}


def fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    """
    Fetch latest closing prices from yfinance.
    Returns a dict of {ticker: price}. Missing tickers are omitted.
    """
    if not tickers:
        return {}
    try:
        import yfinance as yf

        data = yf.download(tickers, period="5d", auto_adjust=True, progress=False)
        if data.empty:
            return {}

        close = data["Close"] if "Close" in data.columns else data
        if isinstance(close, pd.Series):
            series = close.dropna()
            return {tickers[0]: float(series.iloc[-1])} if not series.empty else {}

        result = {}
        for ticker in tickers:
            if ticker in close.columns:
                series = close[ticker].dropna()
                if not series.empty:
                    result[ticker] = float(series.iloc[-1])
        return result
    except Exception:
        return {}


def get_portfolio_history(
    conn: duckdb.DuckDBPyConnection,
    accounts: list[str] | None = None,
) -> pd.DataFrame:
    """
    Last balance of each month per investment account.
    Returns DataFrame: month (YYYY-MM str), account, balance (float).
    """
    accts = accounts or _INVESTMENT_ACCOUNTS
    placeholders = ", ".join("?" * len(accts))
    return conn.execute(f"""
        WITH ranked AS (
            SELECT
                strftime('%Y-%m', date) AS month,
                account,
                CAST(balance AS DOUBLE) AS balance,
                ROW_NUMBER() OVER (
                    PARTITION BY strftime('%Y-%m', date), account
                    ORDER BY date DESC
                ) AS rn
            FROM account_balances
            WHERE account IN ({placeholders})
        )
        SELECT month, account, balance
        FROM ranked
        WHERE rn = 1
        ORDER BY month, account
    """, accts).df()


def get_holdings(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Net shares and cost basis per ticker from investment_transactions.

    Returns DataFrame: symbol, shares, cost_basis, avg_cost_per_share.
    Returns empty DataFrame if no data.
    """
    df = conn.execute("""
        SELECT
            symbol,
            -- shares: all acquisitions including dividend reinvestments
            SUM(CASE WHEN action_type IN ('BUY', 'REINVESTMENT')
                     THEN COALESCE(quantity, 0) ELSE 0 END)
            - SUM(CASE WHEN action_type = 'SELL'
                       THEN COALESCE(quantity, 0) ELSE 0 END)
            AS shares,
            -- cost_basis: BUY only — reinvested dividends are not new capital
            SUM(CASE WHEN action_type = 'BUY'
                     THEN ABS(COALESCE(amount, 0)) ELSE 0 END)
            - SUM(CASE WHEN action_type = 'SELL'
                       THEN ABS(COALESCE(amount, 0)) ELSE 0 END)
            AS cost_basis
        FROM investment_transactions
        WHERE symbol IS NOT NULL AND symbol != ''
          AND action_type IN ('BUY', 'SELL', 'REINVESTMENT')
        GROUP BY symbol
        HAVING shares > 0.0001
        ORDER BY cost_basis DESC
    """).df()

    if not df.empty:
        df["shares"] = df["shares"].astype(float)
        df["cost_basis"] = df["cost_basis"].astype(float)
        df["avg_cost_per_share"] = df["cost_basis"] / df["shares"]

    return df


def get_contributions_history(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Daily contributions from BUY/REINVESTMENT transactions with cumulative total.
    Returns DataFrame: date, daily_contributions, cumulative_contributions.
    """
    df = conn.execute("""
        SELECT
            run_date AS date,
            SUM(ABS(COALESCE(amount, 0))) AS daily_contributions
        FROM investment_transactions
        WHERE action_type = 'BUY'
          AND amount IS NOT NULL
        GROUP BY run_date
        ORDER BY run_date
    """).df()

    if not df.empty:
        df["daily_contributions"] = df["daily_contributions"].astype(float)
        df["cumulative_contributions"] = df["daily_contributions"].cumsum()

    return df


def get_brokerage_value_history(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Reconstruct monthly brokerage portfolio value from investment_transactions
    and yfinance historical prices.

    For each month, computes net shares held per ticker (cumulative BUYs +
    REINVESTMENTs - SELLs up to that month) then multiplies by the closing
    price for that month. SPAXX (money market) defaults to $1/share if yfinance
    has no data.

    Returns DataFrame: month (YYYY-MM), value (float).
    """
    import yfinance as yf

    tx = conn.execute("""
        SELECT run_date AS date, symbol, action_type,
               CAST(COALESCE(quantity, 0) AS DOUBLE) AS quantity
        FROM investment_transactions
        WHERE symbol IS NOT NULL AND symbol != ''
          AND action_type IN ('BUY', 'SELL', 'REINVESTMENT')
        ORDER BY run_date
    """).df()

    if tx.empty:
        return pd.DataFrame(columns=["month", "value"])

    tx["date"] = pd.to_datetime(tx["date"])
    tickers = tx["symbol"].unique().tolist()
    first_date = tx["date"].min()

    # Download full monthly price history for all tickers at once
    raw = yf.download(
        tickers, start=first_date.strftime("%Y-%m-%d"),
        interval="1mo", auto_adjust=True, progress=False,
    )
    close = raw["Close"] if "Close" in raw.columns else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    # Normalise index to YYYY-MM strings, keeping last entry per month,
    # then forward-fill so gaps (e.g. incomplete current month) use last known price.
    close.index = pd.to_datetime(close.index).strftime("%Y-%m")
    close = close[~close.index.duplicated(keep="last")].ffill()

    # Live prices for the current month so the final point matches the summary tiles
    current_month = pd.Timestamp.today().strftime("%Y-%m")
    non_money_market = [t for t in tickers if t not in {"SPAXX"}]
    live_prices = fetch_current_prices(non_money_market)

    _MONEY_MARKET = {"SPAXX"}

    # Build monthly range from first transaction through current month
    months = pd.date_range(
        start=first_date.to_period("M").to_timestamp(),
        end=pd.Timestamp.today(),
        freq="MS",
    ).strftime("%Y-%m").tolist()

    results = []
    for month in months:
        cutoff = pd.Timestamp(month) + pd.offsets.MonthEnd(1)
        sub = tx[tx["date"] <= cutoff]
        value = 0.0
        for ticker in tickers:
            t = sub[sub["symbol"] == ticker]
            shares = (
                t[t["action_type"].isin(["BUY", "REINVESTMENT"])]["quantity"].sum()
                - t[t["action_type"] == "SELL"]["quantity"].sum()
            )
            if shares < 0.0001:
                continue
            if ticker in _MONEY_MARKET:
                price = 1.0
            elif month == current_month and ticker in live_prices:
                price = live_prices[ticker]
            elif month in close.index and ticker in close.columns:
                p = close.loc[month, ticker]
                price = float(p) if pd.notna(p) else None
            else:
                price = None
            if price is None:
                continue
            value += float(shares) * price
        results.append({"month": month, "value": value})

    return pd.DataFrame(results)


def get_dividends(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Dividend income records.
    Returns DataFrame: date, symbol, amount (float).
    """
    return conn.execute("""
        SELECT
            run_date AS date,
            COALESCE(symbol, description) AS symbol,
            CAST(ABS(amount) AS DOUBLE) AS amount
        FROM investment_transactions
        WHERE action_type = 'DIVIDEND'
          AND amount IS NOT NULL
        ORDER BY run_date DESC
    """).df()
