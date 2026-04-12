import marimo

__generated_with = "0.22.4"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from pymoney.db import get_connection

    conn = get_connection()
    return (conn,)


@app.cell
def _(conn, mo):
    _transactions = mo.sql(
        """
        SELECT date, description, amount, category, account, institution
        FROM transactions
        ORDER BY date DESC, id DESC
        """,
        engine=conn
    )
    return


if __name__ == "__main__":
    app.run()
