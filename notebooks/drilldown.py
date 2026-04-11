import marimo

__generated_with = "0.22.4"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from pymoney.budget import sync_budget
    from pymoney.categorize.rules import sync_categories
    from pymoney.db import get_connection

    conn = get_connection()
    sync_categories(conn)
    sync_budget(conn)
    return (conn,)


@app.cell
def _(mo):
    mo.md("""
    ## Transactions
    """)
    return


@app.cell
def _(conn, mo):
    _transactions = mo.sql(
        """
        SELECT
            date,
            description,
            amount,
            category,
            account,
            institution
        FROM transactions
        ORDER BY date DESC, id DESC
        """,
        engine=conn,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Filtered View
    """)
    return


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

    cat_filter = mo.ui.dropdown(_categories, value="All", label="Category")
    acct_filter = mo.ui.dropdown(_accounts, value="All", label="Account")
    search_filter = mo.ui.text(placeholder="Search description…", label="Description")
    limit_filter = mo.ui.dropdown(["100", "500", "1000", "All"], value="100", label="Limit")

    mo.hstack([cat_filter, acct_filter, search_filter, limit_filter], gap="1rem")
    return acct_filter, cat_filter, limit_filter, search_filter


@app.cell
def _(acct_filter, cat_filter, conn, limit_filter, mo, search_filter):
    _where = ["1=1"]
    _params = []

    if cat_filter.value != "All":
        _where.append("category = ?")
        _params.append(cat_filter.value)

    if acct_filter.value != "All":
        _where.append("account = ?")
        _params.append(acct_filter.value)

    if search_filter.value.strip():
        _where.append("description ILIKE ?")
        _params.append(f"%{search_filter.value.strip()}%")

    _limit = "" if limit_filter.value == "All" else f"LIMIT {limit_filter.value}"

    _df = conn.execute(f"""
        SELECT date, description, amount, category, account, institution
        FROM transactions
        WHERE {' AND '.join(_where)}
        ORDER BY date DESC, id DESC
        {_limit}
    """, _params).df()

    _net = _df["amount"].sum() if not _df.empty else 0

    mo.vstack([
        mo.md(f"**{len(_df):,} transactions** · net `${_net:,.2f}`"),
        mo.ui.table(_df, selection=None),
    ])
    return


if __name__ == "__main__":
    app.run()
